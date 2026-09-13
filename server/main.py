"""
Prazo60 - servidor web.

Responsabilidades:
  1. Autenticacao (usuario unico, hash PBKDF2, sessao assinada em cookie HttpOnly).
  2. Entregar a aplicacao (web/app) SOMENTE para sessoes validas.
  3. API de agregados (/api/*): nenhum dado individual sai do servidor.
  4. Cabecalhos de seguranca (CSP, HSTS, anti-clickjacking) e limitacao de tentativas.

Rodar localmente:
    uvicorn server.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import math
import re
import time
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from . import analytics, auth, select_ai, simulation
from .settings import ORIGENS_POWERBI, RAIZ, carregar_configuracao

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("prazo60")

cfg = carregar_configuracao()
base = analytics.BaseLocal.carregar(RAIZ / "server" / "data")
limitador_login = auth.LimitadorTentativas(max_eventos=5, janela_segundos=15 * 60)
limitador_ia = auth.LimitadorTentativas(max_eventos=20, janela_segundos=60 * 60)

WEB_APP = (RAIZ / "web" / "app").resolve()
WEB_PUBLIC = (RAIZ / "web" / "public").resolve()

app = FastAPI(
    title="Prazo60 API",
    version="2.0.0",
    docs_url=None if cfg.producao else "/api/docs",
    redoc_url=None,
    openapi_url=None if cfg.producao else "/api/openapi.json",
)

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-src " + " ".join(ORIGENS_POWERBI),
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])


@app.middleware("http")
async def cabecalhos_seguranca(request: Request, call_next):
    resposta = await call_next(request)
    h = resposta.headers
    h["Content-Security-Policy"] = CSP
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "strict-origin-when-cross-origin"
    h["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
    # allow-popups: o login Microsoft do Power BI incorporado abre em janela propria e precisa responder ao iframe.
    h["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    h["X-Robots-Tag"] = "noindex, nofollow"
    if cfg.cookie_seguro:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        h["Cache-Control"] = "no-store"
    return resposta


app.add_middleware(
    SessionMiddleware,
    secret_key=cfg.session_secret,
    session_cookie="prazo60_sessao",
    max_age=cfg.sessao_max_segundos,
    same_site="lax",
    https_only=cfg.cookie_seguro,
)

# ------------------------------------------------------------------ sessao e protecoes


def sessao_valida(request: Request) -> Optional[str]:
    sessao = request.session
    usuario = sessao.get("usuario")
    if not usuario or time.time() - sessao.get("criada_em", 0) > cfg.sessao_max_segundos:
        sessao.clear()
        return None
    return usuario


def exigir_sessao(request: Request) -> str:
    usuario = sessao_valida(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Sessao expirada ou inexistente. Entre novamente.")
    return usuario


def exigir_requisicao_da_aplicacao(request: Request) -> None:
    """
    Protecao CSRF para POST: exige cabecalho customizado (navegadores nao enviam em
    requisicoes cross-site sem preflight CORS, que este servidor nao autoriza) e confere Origin.
    """
    if request.headers.get("x-requested-with") != "prazo60":
        raise HTTPException(status_code=403, detail="Requisicao recusada.")
    origem = request.headers.get("origin")
    if origem and urlparse(origem).netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Origem nao autorizada.")


def ip_cliente(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


# ------------------------------------------------------------------ paginas


@app.get("/", include_in_schema=False)
def raiz(request: Request):
    return RedirectResponse("/app/" if sessao_valida(request) else "/login", status_code=303)


@app.get("/login", include_in_schema=False)
def pagina_login(request: Request):
    if sessao_valida(request):
        return RedirectResponse("/app/", status_code=303)
    return FileResponse(WEB_PUBLIC / "login.html", headers={"Cache-Control": "no-cache"})


@app.get("/app", include_in_schema=False)
def app_sem_barra():
    return RedirectResponse("/app/", status_code=308)


@app.get("/app/{caminho:path}", include_in_schema=False)
def arquivos_aplicacao(caminho: str, request: Request):
    if not sessao_valida(request):
        return RedirectResponse("/login", status_code=303)
    alvo = (WEB_APP / (caminho or "index.html")).resolve()
    if not alvo.is_relative_to(WEB_APP) or not alvo.is_file():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
    return FileResponse(alvo, headers={"Cache-Control": "no-cache"})


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


app.mount("/public", StaticFiles(directory=WEB_PUBLIC), name="public")

# ------------------------------------------------------------------ autenticacao


class LoginEntrada(BaseModel):
    usuario: str = Field(min_length=1, max_length=64)
    senha: str = Field(min_length=1, max_length=128)


@app.post("/api/auth/login")
def login(dados: LoginEntrada, request: Request):
    exigir_requisicao_da_aplicacao(request)
    ip = ip_cliente(request)
    espera = limitador_login.segundos_bloqueado(ip)
    if espera:
        raise HTTPException(status_code=429, detail=f"Muitas tentativas. Aguarde {math.ceil(espera / 60)} min e tente novamente.", headers={"Retry-After": str(espera)})  # noqa: E501

    usuario_ok = auth.textos_iguais(dados.usuario.strip().upper(), cfg.usuario.upper())
    senha_ok = auth.verificar_senha(dados.senha, cfg.senha_hash)  # sempre executa: tempo constante
    if not (usuario_ok and senha_ok):
        limitador_login.registrar(ip)
        log.warning("login recusado ip=%s", ip)
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

    limitador_login.limpar(ip)
    request.session.clear()
    request.session.update({"usuario": cfg.usuario, "criada_em": int(time.time())})
    log.info("login ok usuario=%s ip=%s", cfg.usuario, ip)
    return {"ok": True, "usuario": cfg.usuario}


@app.post("/api/auth/logout")
def logout(request: Request):
    exigir_requisicao_da_aplicacao(request)
    request.session.clear()
    return {"ok": True}


@app.get("/api/auth/sessao")
def sessao(request: Request, usuario: str = Depends(exigir_sessao)):
    return {"usuario": usuario, "expira_em": request.session["criada_em"] + cfg.sessao_max_segundos}


@app.get("/api/saude")
def saude():
    return {"status": "ok", "casos_carregados": len(base.casos), "fonte": "base local minimizada"}


# ------------------------------------------------------------------ dados (autenticado)


def ler_filtros(
    ano: Optional[int] = Query(None, ge=2000, le=2100),
    mes: Optional[int] = Query(None, ge=1, le=12),
    drs: Optional[int] = Query(None, ge=1, le=17),
    municipio: Optional[str] = Query(None, pattern=r"^\d{6}$"),
    cnes: Optional[str] = Query(None, pattern=r"^\d{7}$"),
    tipo: Optional[str] = Query(None, max_length=40),
    situacao: Optional[Literal["dentro", "limite", "acima"]] = None,
    dimensao: Literal["residencia", "tratamento"] = "residencia",
) -> analytics.Filtros:
    if tipo is not None and tipo not in base.tipos:
        raise HTTPException(status_code=422, detail="Tipo de tratamento invalido.")
    if municipio is not None and municipio not in base.municipios:
        raise HTTPException(status_code=422, detail="Municipio invalido.")
    return analytics.Filtros(ano=ano, mes=mes, drs=drs, municipio=municipio, cnes=cnes, tipo=tipo, situacao=situacao, dimensao=dimensao)


@app.get("/api/config", dependencies=[Depends(exigir_sessao)])
def config_publica():
    return {
        "powerbi": {"url": cfg.powerbi_url, "modo": cfg.powerbi_modo, "titulo": cfg.powerbi_titulo},
        "select_ai": {"habilitado": cfg.select_ai_habilitado, "perfil": cfg.select_ai_perfil, "provedor": cfg.select_ai_provedor},
        "ambiente": cfg.ambiente,
    }


_referencia_cache: dict = {}


@app.get("/api/referencia", dependencies=[Depends(exigir_sessao)])
def referencia():
    if not _referencia_cache:
        ref = base.ref
        _referencia_cache.update({
            "meta": ref["meta"],
            "mapa": ref["mapa"],
            "drs": {n: {"nome": d["nome"], "oferta_2025": d["oferta_2025"], "oferta_por_ano": d["oferta_por_ano"]} for n, d in base.drs.items()},
            "municipios": {k: {"nome": m["nome"], "drs": m["drs"], "x": m["x"], "y": m["y"]} for k, m in base.municipios.items()},
            "qualidade_dados": ref["qualidade_dados"],
            "select_ai_evidencia": ref["select_ai_evidencia"],
            "indicadores_info": ref["indicadores_info"],
            "privacidade_etica": ref["privacidade_etica"],
            "apis_futuras": ref["apis_futuras"],
            "alertas_metodologia": ref["alertas_metodologia"],
            "hospitais_referencia_fonte": ref["hospitais_referencia_fonte"],
            "cobertura": {
                "casos": len(base.casos),
                "municipios_sp": len(base.municipios),
                "municipios_com_coordenada": sum(1 for m in base.municipios.values() if m["lat"] is not None),
                "unidades": len(base.unidades),
                "unidades_nome_confirmado": sum(1 for x in base.unidades.values() if x["nome_confirmado"]),
                "unidades_habilitacao_confirmada": sum(1 for x in base.unidades.values() if x["habilitacao"]),
                "tipos_tratamento": base.tipos,
                "anos": base.anos,
                "anos_parciais": base.anos_parciais,
            },
        })
    return _referencia_cache


@app.get("/api/opcoes", dependencies=[Depends(exigir_sessao)])
def opcoes():
    return base.opcoes()


@app.get("/api/painel", dependencies=[Depends(exigir_sessao)])
def painel(filtros: analytics.Filtros = Depends(ler_filtros)):
    dados = base.painel(filtros)
    return {**dados, "recomendacoes": base.recomendacoes(dados)}


@app.get("/api/localizador", dependencies=[Depends(exigir_sessao)])
def localizador(municipio: str = Query(..., pattern=r"^\d{6}$"), limite: int = Query(12, ge=1, le=40)):
    try:
        return base.localizador(municipio, limite)
    except analytics.DadosInsuficientes as erro:
        raise HTTPException(status_code=422, detail=str(erro))


@app.get("/api/simulacao/contexto", dependencies=[Depends(exigir_sessao)])
def contexto_simulacao(municipio: str = Query(..., pattern=r"^\d{6}$")):
    try:
        return simulation.contexto(base, municipio)
    except analytics.DadosInsuficientes as erro:
        raise HTTPException(status_code=422, detail=str(erro))


class SimulacaoEntrada(BaseModel):
    municipio: str = Field(pattern=r"^\d{6}$")
    cenario: Literal["capacidade_normal", "demanda_elevada", "unidade_indisponivel", "aumento_demanda", "redistribuicao_regional"]
    aumento_pct: float = Field(20, ge=0, le=100)
    percentual: float = Field(30, ge=5, le=100)
    cnes: Optional[str] = Field(None, pattern=r"^\d{7}$")
    destino: Optional[str] = Field(None, pattern=r"^\d{7}$")
    utilizacao_base: float = Field(simulation.PREMISSAS_PADRAO["utilizacao_base"], ge=0.50, le=0.94)
    fracao_fila: float = Field(0.50, ge=0.10, le=0.90)


@app.post("/api/simulacao", dependencies=[Depends(exigir_sessao)])
def executar_simulacao(dados: SimulacaoEntrada, request: Request):
    exigir_requisicao_da_aplicacao(request)
    try:
        return simulation.simular(base, dados.municipio, dados.cenario, dados.model_dump(exclude={"municipio", "cenario"}))
    except analytics.DadosInsuficientes as erro:
        raise HTTPException(status_code=422, detail=str(erro))


class PerguntaEntrada(BaseModel):
    pergunta: str = Field(min_length=5, max_length=500)


@app.post("/api/ia/perguntar")
def perguntar(dados: PerguntaEntrada, request: Request, usuario: str = Depends(exigir_sessao)):
    exigir_requisicao_da_aplicacao(request)
    if not cfg.select_ai_habilitado:
        return JSONResponse(status_code=503, content={
            "status": "nao_configurado",
            "detail": "A integração com o Oracle Select AI ainda não está configurada neste ambiente. Nenhuma resposta foi gerada.",
            "requisitos": ["SELECT_AI_HABILITADO=true", "ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN e ORACLE_WALLET_DIR no servidor", f"perfil {cfg.select_ai_perfil} criado com DBMS_CLOUD_AI.CREATE_PROFILE"],
        })
    chave = f"{usuario}:{ip_cliente(request)}"
    if limitador_ia.segundos_bloqueado(chave):
        raise HTTPException(status_code=429, detail="Limite de perguntas por hora atingido.")
    limitador_ia.registrar(chave)
    try:
        return select_ai.perguntar(dados.pergunta.strip(), cfg.select_ai_perfil)
    except select_ai.SelectAINaoConfigurado as erro:
        raise HTTPException(status_code=503, detail=str(erro))
    except select_ai.ProvedorIndisponivel:
        raise HTTPException(status_code=503, detail="O modelo de IA (Google Gemini) está sobrecarregado, lento ou no limite de uso agora. Aguarde alguns segundos e pergunte de novo.")
    except select_ai.ConsultaRecusada as erro:
        raise HTTPException(status_code=422, detail=str(erro))
    except Exception as erro:
        # Mensagens do provedor (ex.: Google) trazem a URL com ?key=...: nunca registrar a chave no log.
        log.error("falha no Select AI: %s", re.sub(r"key=[^&\s]+", "key=***", str(erro)))
        raise HTTPException(status_code=502, detail="O banco não conseguiu responder à pergunta agora.")


@app.exception_handler(404)
async def nao_encontrado(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": getattr(exc, "detail", "Nao encontrado.")})
    return RedirectResponse("/", status_code=303)
