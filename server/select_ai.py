"""
Integracao com Oracle Select AI (DBMS_CLOUD_AI).

Desligada por padrao. So e ativada quando SELECT_AI_HABILITADO=true E as variaveis
ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN e ORACLE_WALLET_DIR estao definidas no servidor.
Sem isso, o endpoint responde 503 com o motivo; nenhuma resposta e inventada.

Fluxo por pergunta:
  1. DBMS_CLOUD_AI.GENERATE(action => 'showsql') gera o SQL, com um contexto que explica as
     views analiticas VW_P60_* (evolucao, meses, demanda x oferta, rankings com minimo de casos);
  2. o servidor extrai e confere que e uma unica consulta de leitura;
  3. a consulta roda no Oracle com o usuario do site (PRAZO60_APP, que so enxerga views agregadas);
  4. se o modelo nao devolver SQL ou o SQL falhar, pede de novo informando o motivo (ate 3 vezes).

O navegador nunca fala com o banco: Frontend -> /api/ia/perguntar (FastAPI) -> Oracle ADB -> Select AI.
"""

from __future__ import annotations

import datetime
import decimal
import logging
import re
import time

log = logging.getLogger("prazo60")

# Erros passageiros do provedor do modelo: 503 (sobrecarga) e 429 (limite por minuto do plano gratuito).
ERROS_TRANSITORIOS = ("ORA-20503", "ORA-20429")
TENTATIVAS_PROVEDOR = 2
TENTATIVAS_CONSULTA = 3
TEMPO_MAXIMO_MS = 45_000
MAX_LINHAS = 50

# Orienta o modelo a usar as views certas para cada tipo de pergunta (ver 07_camada_analitica_select_ai.sql).
CONTEXTO = (
    "Base Prazo60: casos de câncer de mama (CID C50) no SUS do Estado de São Paulo, diagnósticos de 2022 a 2026 "
    "(2026 é ano parcial). Use somente as views VW_P60_*. Região significa DRS. "
    "Para evolução, piora ou melhora entre anos use VW_P60_DRS_ANO ou a coluna VARIACAO_PP_2024_2025 de VW_P60_DRS "
    "(valor positivo é piora). Para últimos meses ou tendência mensal use VW_P60_RESUMO_MES ordenada por ANO_MES "
    "decrescente. Para demanda x oferta, pressão assistencial ou oferta use VW_P60_DRS "
    "(PRESSAO_CASOS_POR_ESTABELECIMENTO, ESTABELECIMENTOS_2025). Para municípios use VW_P60_MUNICIPIO e para unidades "
    "use VW_P60_UNIDADE. Não existe distância na base: proximidade significa mesma DRS. "
    "Percentual acima de 60 dias é a coluna PCT_ACIMA_60. Limite rankings a 10 linhas quando a pergunta não disser quantas. "
    "Meses de 2026 estão incompletos (casos recentes ainda não iniciaram tratamento): para últimos meses use os meses "
    "de 2025 (ANO = 2025), salvo se a pergunta citar 2026. Ao comparar regiões exclua COD_DRS = 'DRS-00' "
    "(Fora do Estado de SP). Ao juntar views, use SELECT DISTINCT para não repetir linhas. "
)


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


def _gerar_sql(cursor, prompt: str, perfil: str) -> str:
    for tentativa in range(TENTATIVAS_PROVEDOR):
        try:
            # O perfil define o modelo e as views permitidas; a pergunta vai como bind, nunca concatenada no SQL.
            cursor.execute(
                "SELECT DBMS_CLOUD_AI.GENERATE(prompt => :prompt, profile_name => :perfil, action => 'showsql') FROM dual",
                prompt=prompt, perfil=perfil,
            )
            return (_ler(cursor.fetchone()[0]) or "").strip()
        except Exception as erro:
            texto = str(erro)
            if "DPY-4024" in texto:  # tempo maximo da chamada esgotado
                raise ProvedorIndisponivel("O modelo de linguagem demorou demais para responder.") from erro
            if not any(codigo in texto for codigo in ERROS_TRANSITORIOS):
                raise
            if tentativa == TENTATIVAS_PROVEDOR - 1:
                raise ProvedorIndisponivel("Modelo de linguagem sobrecarregado ou no limite de uso.") from erro
            time.sleep(3)
    raise ProvedorIndisponivel("Modelo de linguagem indisponivel.")


def _extrair_consulta(texto: str) -> str | None:
    """
    Aceita o SQL puro ou dentro de bloco ```sql```, com texto antes. Devolve None quando nao ha
    uma unica consulta de leitura (SELECT/WITH no inicio de uma linha, sem comandos encadeados).
    """
    conteudo = (texto or "").strip()
    bloco = re.search(r"```(?:sql)?\s*(.*?)```", conteudo, re.S | re.I)
    if bloco:
        conteudo = bloco.group(1).strip()
    inicio = re.search(r"(?im)^\s*(with|select)\b", conteudo)
    if not inicio:
        return None
    consulta = conteudo[inicio.start():].strip().rstrip(";").strip()
    return None if ";" in consulta else consulta


def perguntar(pergunta: str, perfil: str) -> dict:
    try:
        from .oracle.database import get_connection  # importado so aqui: cria o pool Oracle
    except (ImportError, KeyError) as erro:
        raise SelectAINaoConfigurado(f"Conexao Oracle indisponivel: {erro}") from erro

    with get_connection() as conn:
        conn.call_timeout = TEMPO_MAXIMO_MS
        cursor = conn.cursor()
        observacao = ""
        for tentativa in range(1, TENTATIVAS_CONSULTA + 1):
            sql_gerado = _gerar_sql(cursor, f"{CONTEXTO}{observacao}Pergunta: {pergunta}", perfil)
            consulta = _extrair_consulta(sql_gerado)
            if not consulta:
                log.info("Select AI sem SQL valido (tentativa %s): %.160s", tentativa, sql_gerado.replace("\n", " "))
                observacao = "Responda obrigatoriamente com uma consulta SQL de leitura, a mais próxima possível da pergunta. "
                continue
            try:
                cursor.execute(consulta)
                colunas = [c[0] for c in cursor.description]
                linhas = [[_serializar(v) for v in linha] for linha in cursor.fetchmany(MAX_LINHAS + 1)]
            except Exception as erro:
                if "DPY-4024" in str(erro):
                    raise ProvedorIndisponivel("A consulta demorou demais no banco.") from erro
                codigo = re.search(r"(ORA|DPY)-\d{4,5}", str(erro))
                codigo = codigo.group(0) if codigo else "erro"
                log.info("SQL gerado falhou no banco (tentativa %s, %s): %.160s", tentativa, codigo, consulta.replace("\n", " "))
                observacao = f"A consulta anterior falhou no Oracle com {codigo}: use somente views e colunas que existem. "
                continue
            return {
                "pergunta": pergunta,
                "sql_gerado": consulta,
                "colunas": colunas,
                "linhas": linhas[:MAX_LINHAS],
                "truncado": len(linhas) > MAX_LINHAS,
                "perfil": perfil,
                "fonte": "SQL gerado pelo Select AI e executado no Oracle Autonomous Database (usuário somente leitura, apenas dados agregados)",
            }

    raise ConsultaRecusada("A IA não conseguiu responder essa pergunta com os dados do Prazo60. Tente uma das perguntas sugeridas ou reformule com mais detalhes.")
