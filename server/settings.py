"""
Configuracao centralizada. Tudo que muda entre ambientes vem de variavel de ambiente.

Nenhuma senha em texto puro fica no codigo: o usuario unico (DATAHOLICS) e validado
contra um hash PBKDF2-SHA256. Para trocar a senha, gere um novo hash com
`python scripts/gerar_hash_senha.py` e defina APP_PASSWORD_HASH no painel do Render.
"""

from __future__ import annotations

import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

RAIZ = Path(__file__).resolve().parents[1]

try:  # .env so e usado em desenvolvimento local
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

USUARIO_PADRAO = "DATAHOLICS"
# Hash PBKDF2 da senha definida pelo grupo. Gerado por scripts/gerar_hash_senha.py.
SENHA_HASH_PADRAO = "pbkdf2_sha256$600000$66veWX41XDILl84pbyYxIA==$kZAQjhsi1LZpC8Sy48buWJ0bIdXg3kWh55JqZfObO+U="

ORIGENS_POWERBI = ("https://app.powerbi.com", "https://app.fabric.microsoft.com")


def normalizar_powerbi(url: str | None) -> tuple[str | None, str | None]:
    """
    Aceita qualquer um dos links do Power BI e devolve (url_de_incorporacao, modo).

    - Link copiado da barra do navegador (/groups/<workspace>/reports/<id>/<pagina>): essa pagina
      nao pode ser exibida em iframe, entao e convertida para /reportEmbed (modo "seguro").
    - /reportEmbed (Inserir > Site ou portal): usado como esta (modo "seguro", exige login Microsoft).
    - /view?r= (Publicar na Web): usado como esta (modo "publico").
    """
    if not url or not url.strip():
        return None, None
    partes = urlparse(url.strip())
    origem = f"{partes.scheme}://{partes.netloc}"
    if origem not in ORIGENS_POWERBI:
        raise RuntimeError("POWERBI_EMBED_URL deve apontar para https://app.powerbi.com ou https://app.fabric.microsoft.com.")
    consulta = parse_qs(partes.query)

    if partes.path.startswith("/view"):
        return url.strip(), "publico"
    if partes.path.startswith("/reportEmbed"):
        return url.strip(), "seguro"

    rota = re.match(r"^/groups/([^/]+)/reports/([0-9a-fA-F-]{36})(?:/([^/?#]+))?", partes.path)
    if rota:
        workspace, relatorio, pagina = rota.groups()
        params = {"reportId": relatorio, "autoAuth": "true"}
        if workspace != "me":
            params["groupId"] = workspace
        if pagina:
            params["pageName"] = pagina
        if "ctid" in consulta:
            params["ctid"] = consulta["ctid"][0]
        return f"{origem}/reportEmbed?{urlencode(params)}", "seguro"

    raise RuntimeError("POWERBI_EMBED_URL nao reconhecido. Use o link do relatorio, o de 'Inserir relatorio > Site ou portal' ou o de 'Publicar na Web'.")


def _bool(nome: str, padrao: bool) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes"}


@dataclass(frozen=True)
class Configuracao:
    ambiente: str
    usuario: str
    senha_hash: str
    session_secret: str
    cookie_seguro: bool
    sessao_max_segundos: int
    powerbi_url: str | None
    powerbi_modo: str | None
    powerbi_titulo: str
    select_ai_habilitado: bool
    select_ai_perfil: str
    select_ai_provedor: str

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"


def carregar_configuracao() -> Configuracao:
    ambiente = os.environ.get("PRAZO60_AMBIENTE") or ("producao" if os.environ.get("RENDER") else "desenvolvimento")

    segredo = os.environ.get("SESSION_SECRET")
    if not segredo:
        if ambiente == "producao":
            raise RuntimeError("SESSION_SECRET e obrigatorio em producao (o render.yaml gera um automaticamente).")
        # Em desenvolvimento, um segredo aleatorio por execucao: reiniciar o servidor desloga.
        segredo = secrets.token_urlsafe(48)

    powerbi_url, powerbi_modo = normalizar_powerbi(os.environ.get("POWERBI_EMBED_URL"))

    oracle_configurado = all(os.environ.get(v) for v in ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN", "ORACLE_WALLET_DIR"))

    return Configuracao(
        ambiente=ambiente,
        usuario=os.environ.get("APP_USER", USUARIO_PADRAO),
        senha_hash=os.environ.get("APP_PASSWORD_HASH", SENHA_HASH_PADRAO),
        session_secret=segredo,
        cookie_seguro=_bool("COOKIE_SECURE", ambiente == "producao"),
        sessao_max_segundos=int(os.environ.get("SESSION_MAX_HOURS", "8")) * 3600,
        powerbi_url=powerbi_url,
        powerbi_modo=powerbi_modo,
        powerbi_titulo=os.environ.get("POWERBI_TITULO", "Relatorio Prazo60"),
        select_ai_habilitado=_bool("SELECT_AI_HABILITADO", False) and oracle_configurado,
        select_ai_perfil=os.environ.get("SELECT_AI_PERFIL", "PRAZO60_AI_GOOGLE"),
        select_ai_provedor=os.environ.get("SELECT_AI_PROVEDOR", "Google Gemini (gemini-flash-lite-latest)"),
    )
