"""
Testes automatizados da plataforma Prazo60.

    python -m pytest -q
"""

import os

os.environ.setdefault("PRAZO60_AMBIENTE", "teste")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server import main  # noqa: E402

H = {"X-Requested-With": "prazo60"}
LOGIN = {"usuario": "DATAHOLICS", "senha": "PRAZO60"}


@pytest.fixture(autouse=True)
def limpar_limitadores():
    main.limitador_login.limpar()
    main.limitador_ia.limpar()
    yield


@pytest.fixture
def cliente():
    return TestClient(main.app)


@pytest.fixture
def logado(cliente):
    r = cliente.post("/api/auth/login", json=LOGIN, headers=H)
    assert r.status_code == 200, r.text
    return cliente


# ------------------------------------------------------------------ autenticacao

def test_senha_nunca_em_texto_puro():
    assert "PRAZO60" not in main.cfg.senha_hash
    assert main.cfg.senha_hash.startswith("pbkdf2_sha256$600000$")


def test_login_valido_e_usuario_sem_diferenciar_maiusculas(cliente):
    r = cliente.post("/api/auth/login", json={"usuario": "dataholics", "senha": "PRAZO60"}, headers=H)
    assert r.status_code == 200
    assert "prazo60_sessao" in r.cookies
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie


@pytest.mark.parametrize("dados", [{"usuario": "DATAHOLICS", "senha": "prazo60"}, {"usuario": "OUTRO", "senha": "PRAZO60"}, {"usuario": "DATAHOLICS", "senha": "errada"}])
def test_login_invalido(cliente, dados):
    r = cliente.post("/api/auth/login", json=dados, headers=H)
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuário ou senha inválidos."


def test_login_exige_cabecalho_csrf(cliente):
    assert cliente.post("/api/auth/login", json=LOGIN).status_code == 403
    r = cliente.post("/api/auth/login", json=LOGIN, headers={**H, "Origin": "https://site-malicioso.example"})
    assert r.status_code == 403


def test_limite_de_tentativas(cliente):
    for _ in range(5):
        assert cliente.post("/api/auth/login", json={"usuario": "DATAHOLICS", "senha": "x"}, headers=H).status_code == 401
    bloqueado = cliente.post("/api/auth/login", json=LOGIN, headers=H)
    assert bloqueado.status_code == 429
    assert "Retry-After" in bloqueado.headers


def test_logout_encerra_sessao(logado):
    assert logado.get("/api/auth/sessao").status_code == 200
    assert logado.post("/api/auth/logout", headers=H).status_code == 200
    assert logado.get("/api/auth/sessao").status_code == 401


# ------------------------------------------------------------------ protecao de rotas

@pytest.mark.parametrize("rota", ["/api/painel", "/api/referencia", "/api/opcoes", "/api/config", "/api/localizador?municipio=354870", "/api/simulacao/contexto?municipio=354870"])
def test_api_exige_login(cliente, rota):
    assert cliente.get(rota).status_code == 401


def test_aplicacao_redireciona_sem_login(cliente):
    r = cliente.get("/app/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert cliente.get("/app/js/app.js", follow_redirects=False).status_code == 303


def test_travessia_de_diretorio_bloqueada(logado):
    r = logado.get("/app/..%2f..%2fserver%2fsettings.py", follow_redirects=False)
    assert r.status_code in (303, 404)
    assert "SENHA_HASH" not in r.text


def test_base_de_casos_nao_e_publica(cliente, logado):
    for c in (cliente, logado):
        for rota in ("/public/../server/data/casos.csv.gz", "/server/data/casos.csv.gz", "/app/../server/data/casos.csv.gz"):
            r = c.get(rota, follow_redirects=False)
            assert r.status_code != 200 or b"mun_res" not in r.content


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/login")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "noindex" in r.headers["x-robots-tag"]


# ------------------------------------------------------------------ dados

def test_kpis_batem_com_site_anterior(logado):
    k = logado.get("/api/painel").json()["kpis"]
    assert (k["n"], k["pct_fora_60"], k["pct_dentro_60"], k["mediana_dias"], k["media_dias"], k["maior_tempo_dias"]) == (45416, 61.3, 38.7, 79.0, 112.1, 1443)


def test_alertas_batem_com_classificacao_publicada(logado):
    alertas = {a["drs"]: a["classificacao"] for a in logado.get("/api/painel").json()["alertas"]}
    assert alertas[5] == "CRITICO" and alertas[14] == "CRITICO" and alertas[12] == "CRITICO"
    assert alertas[3] == "ATENCAO" and alertas[9] == "OPORTUNIDADE" and alertas[1] == "MONITORAR"


def test_faixas_somam_total(logado):
    p = logado.get("/api/painel").json()
    assert sum(f["quantidade"] for f in p["faixas"]) == p["kpis"]["n"]
    assert sum(s["quantidade"] for s in p["situacao"].values()) == p["kpis"]["n"]


def test_filtros_combinados_e_supressao(logado):
    p = logado.get("/api/painel", params={"ano": 2024, "drs": 7, "tipo": "Quimioterapia"}).json()
    assert 0 < p["kpis"]["n"] < 45416
    pequenos = [m for m in p["por_municipio"] if m["suprimido"]]
    assert pequenos and all(m["n"] is None and m["pct_fora_60"] is None for m in pequenos)


def test_filtro_invalido_recusado(logado):
    assert logado.get("/api/painel", params={"tipo": "Inexistente"}).status_code == 422
    assert logado.get("/api/painel", params={"municipio": "999999"}).status_code == 422
    assert logado.get("/api/painel", params={"drs": 99}).status_code == 422


def test_nenhum_campo_individual_na_api(logado):
    texto = logado.get("/api/painel").text + logado.get("/api/referencia").text
    for proibido in ("data_nascimento", "cod_caso", "CASO-0", "cns"):
        assert proibido not in texto.lower() or proibido == "cns" and "cns_preenchido" in texto


def test_recomendacoes_tem_fundamento(logado):
    recs = logado.get("/api/painel").json()["recomendacoes"]
    assert {r["tipo"] for r in recs} >= {"ATENCAO", "RISCO", "OPORTUNIDADE", "ACAO_SUGERIDA"}
    assert all(r["fundamento"] for r in recs)


# ------------------------------------------------------------------ localizador e simulacao

def test_localizador_sao_bernardo(logado):
    r = logado.get("/api/localizador", params={"municipio": "354870"}).json()
    assert r["origem"]["nome"] == "São Bernardo do Campo"
    assert r["unidades"][0]["distancia_km"] <= 10
    assert "não confirma vaga" in r["aviso_disponibilidade"]
    distancias = [u["faixa_distancia"] for u in r["unidades"]]
    assert distancias[0] == "até 10 km"


@pytest.mark.parametrize("cenario", ["capacidade_normal", "demanda_elevada", "unidade_indisponivel", "aumento_demanda", "redistribuicao_regional"])
def test_simulacao_todos_cenarios(logado, cenario):
    r = logado.post("/api/simulacao", json={"municipio": "354870", "cenario": cenario}, headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["tipo_resultado"] == "SIMULACAO"
    assert d["limitacoes"] and d["dados_necessarios"] and d["premissas"]
    if cenario == "capacidade_normal":
        assert d["resultado_origem"]["variacao_mediana_dias"] == 0


def test_simulacao_municipio_pequeno_recusado(logado):
    r = logado.post("/api/simulacao", json={"municipio": "350020", "cenario": "capacidade_normal"}, headers=H)
    assert r.status_code == 422


def test_powerbi_link_do_navegador_vira_embed():
    from server.settings import normalizar_powerbi

    url, modo = normalizar_powerbi("https://app.powerbi.com/groups/me/reports/0a799b85-3b20-4162-81b6-d3a61ba73ff7/d1bb6caba29ffc924e85?experience=power-bi")
    assert modo == "seguro"
    assert url == "https://app.powerbi.com/reportEmbed?reportId=0a799b85-3b20-4162-81b6-d3a61ba73ff7&autoAuth=true&pageName=d1bb6caba29ffc924e85"
    assert normalizar_powerbi("https://app.powerbi.com/view?r=abc")[1] == "publico"
    assert normalizar_powerbi("")[0] is None
    with pytest.raises(RuntimeError):
        normalizar_powerbi("https://site-malicioso.example/reportEmbed?reportId=x")


def test_extracao_sql_do_select_ai():
    from server.select_ai import _extrair_consulta

    assert _extrair_consulta("SELECT 1 FROM dual") == "SELECT 1 FROM dual"
    assert _extrair_consulta("```sql\nSELECT 1 FROM dual;\n```") == "SELECT 1 FROM dual"
    assert _extrair_consulta("Aqui esta a consulta:\nWITH a AS (SELECT 1 x FROM dual) SELECT x FROM a").startswith("WITH")
    assert _extrair_consulta("Sorry, unfortunately a valid SELECT statement could not be generated") is None
    assert _extrair_consulta("SELECT 1 FROM dual; DELETE FROM TB_DRS") is None


def test_ia_nao_inventa_resposta(logado):
    r = logado.post("/api/ia/perguntar", json={"pergunta": "Qual regiao tem maior risco?"}, headers=H)
    assert r.status_code == 503
    assert r.json()["status"] == "nao_configurado"
