"""
Aponta o perfil de IA do site (PRAZO60_AI_GOOGLE, no usuario PRAZO60_APP) para as views
agregadas VW_P60_* e testa perguntas tipicas. Rodar depois do 07_camada_analitica_select_ai.sql.

    python scripts/atualizar_perfil_views.py

Usa as variaveis ORACLE_* do .env. Nao precisa da chave do Google (a credencial ja existe no banco).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from server import select_ai  # noqa: E402
from server.oracle.database import get_connection  # noqa: E402

PERFIL = os.environ.get("SELECT_AI_PERFIL", "PRAZO60_AI_GOOGLE")
VIEWS = ["VW_P60_RESUMO_ANO", "VW_P60_RESUMO_MES", "VW_P60_DRS", "VW_P60_DRS_ANO",
         "VW_P60_MUNICIPIO", "VW_P60_UNIDADE", "VW_P60_TIPO_TRATAMENTO", "VW_P60_FAIXA_DIAS"]

PERGUNTAS = [
    "Qual região apresentou pior evolução?",
    "Como a situação mudou nos últimos meses?",
    "Onde existe maior pressão entre demanda e oferta?",
    "Quais unidades estão próximas de municípios críticos?",
    "Quais municípios possuem maior percentual acima de 60 dias?",
    "Quantos casos ultrapassaram o prazo de 60 dias?",
]

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM all_views WHERE owner = 'ADMIN' AND view_name LIKE 'VW_P60_%' AND view_name <> 'VW_P60_BASE'")
    print("views agregadas visiveis para o usuario do site:", cur.fetchone()[0], "(esperado 8)")
    cur.callproc("DBMS_CLOUD_AI.SET_ATTRIBUTE", [PERFIL, "object_list", json.dumps([{"owner": "ADMIN", "name": v} for v in VIEWS])])
    cur.callproc("DBMS_CLOUD_AI.SET_ATTRIBUTE", [PERFIL, "comments", "true"])
    print(f"perfil {PERFIL} atualizado: 8 views, comentarios ligados")

falhas = 0
for pergunta in PERGUNTAS:
    inicio = time.time()
    try:
        r = select_ai.perguntar(pergunta, PERFIL)
        print(f"\n[OK] {pergunta} ({time.time() - inicio:.1f}s)")
        print("   colunas:", r["colunas"])
        for linha in r["linhas"][:4]:
            print("   ", linha)
        print("   SQL:", re.sub(r"\s+", " ", r["sql_gerado"])[:240])
    except Exception as erro:
        falhas += 1
        print(f"\n[FALHA] {pergunta} ({time.time() - inicio:.1f}s): {type(erro).__name__}: {re.sub(r'key=[^&\s]+', 'key=***', str(erro))[:220]}")
    time.sleep(4)

print(f"\n{len(PERGUNTAS) - falhas} de {len(PERGUNTAS)} perguntas respondidas.")
