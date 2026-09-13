"""
Integracao com Oracle Select AI (DBMS_CLOUD_AI).

Desligada por padrao. So e ativada quando SELECT_AI_HABILITADO=true E as variaveis
ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN e ORACLE_WALLET_DIR estao definidas no servidor.
Sem isso, o endpoint responde 503 com o motivo; nenhuma resposta e inventada.

Fluxo (uma unica chamada ao modelo de linguagem por pergunta):
  1. DBMS_CLOUD_AI.GENERATE(action => 'showsql') gera o SQL a partir da pergunta;
  2. o servidor confere que e uma consulta de leitura;
  3. a consulta roda no Oracle com o usuario do site (PRAZO60_APP, somente SELECT em 7 objetos,
     sem data de nascimento) e o resultado real volta para a tela junto com o SQL.

O navegador nunca fala com o banco: Frontend -> /api/ia/perguntar (FastAPI) -> Oracle ADB -> Select AI.
"""

from __future__ import annotations

import datetime
import decimal
import re
import time

# Erros passageiros do provedor do modelo: 503 (sobrecarga) e 429 (limite por minuto do plano gratuito).
ERROS_TRANSITORIOS = ("ORA-20503", "ORA-20429")
TENTATIVAS = 2
TEMPO_MAXIMO_MS = 45_000
MAX_LINHAS = 50


class SelectAINaoConfigurado(RuntimeError):
    pass


class ProvedorIndisponivel(RuntimeError):
    """O modelo de linguagem recusou ou demorou demais (sobrecarga, limite de uso ou tempo esgotado)."""


class ConsultaRecusada(RuntimeError):
    """A IA nao gerou uma consulta de leitura valida, ou a consulta gerada falhou no banco."""


def _ler(valor):
    return valor.read() if hasattr(valor, "read") else valor


def _serializar(valor):
    valor = _ler(valor)
    if isinstance(valor, decimal.Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.isoformat()
    return valor


def _gerar_sql(cursor, pergunta: str, perfil: str) -> str:
    for tentativa in range(TENTATIVAS):
        try:
            # O perfil define o modelo e as tabelas permitidas; a pergunta vai como bind, nunca concatenada.
            cursor.execute(
                "SELECT DBMS_CLOUD_AI.GENERATE(prompt => :pergunta, profile_name => :perfil, action => 'showsql') FROM dual",
                pergunta=pergunta, perfil=perfil,
            )
            return (_ler(cursor.fetchone()[0]) or "").strip()
        except Exception as erro:
            texto = str(erro)
            if "DPY-4024" in texto:  # tempo maximo da chamada esgotado
                raise ProvedorIndisponivel("O modelo de linguagem demorou demais para responder.") from erro
            if not any(codigo in texto for codigo in ERROS_TRANSITORIOS):
                raise
            if tentativa == TENTATIVAS - 1:
                raise ProvedorIndisponivel("Modelo de linguagem sobrecarregado ou no limite de uso.") from erro
            time.sleep(3)
    raise ProvedorIndisponivel("Modelo de linguagem indisponivel.")


def _validar_leitura(sql: str) -> str:
    consulta = sql.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", consulta) or ";" in consulta:
        raise ConsultaRecusada("A IA não conseguiu transformar essa pergunta em uma consulta aos dados do Prazo60. Tente reformular com mais detalhes.")
    return consulta


def perguntar(pergunta: str, perfil: str) -> dict:
    try:
        from .oracle.database import get_connection  # importado so aqui: cria o pool Oracle
    except (ImportError, KeyError) as erro:
        raise SelectAINaoConfigurado(f"Conexao Oracle indisponivel: {erro}") from erro

    with get_connection() as conn:
        conn.call_timeout = TEMPO_MAXIMO_MS
        cursor = conn.cursor()
        sql_gerado = _gerar_sql(cursor, pergunta, perfil)
        consulta = _validar_leitura(sql_gerado)
        try:
            cursor.execute(consulta)
            colunas = [c[0] for c in cursor.description]
            linhas = [[_serializar(v) for v in linha] for linha in cursor.fetchmany(MAX_LINHAS + 1)]
        except Exception as erro:
            codigo = re.search(r"(ORA|DPY)-\d{4,5}", str(erro))
            raise ConsultaRecusada(
                f"A consulta gerada pela IA não rodou no banco ({codigo.group(0) if codigo else 'erro'}). Tente reformular a pergunta."
            ) from erro

    return {
        "pergunta": pergunta,
        "sql_gerado": consulta,
        "colunas": colunas,
        "linhas": linhas[:MAX_LINHAS],
        "truncado": len(linhas) > MAX_LINHAS,
        "perfil": perfil,
        "fonte": "SQL gerado pelo Select AI e executado no Oracle Autonomous Database (usuário somente leitura)",
    }
