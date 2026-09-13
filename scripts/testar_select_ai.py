"""
Testa, do seu computador, a mesma conexao que o site fara com o Prazo60DB e o Select AI.
Rode ANTES de ligar SELECT_AI_HABILITADO no Render.

    pip install -r requirements.txt
    python scripts/testar_select_ai.py

Le as variaveis ORACLE_* e SELECT_AI_PERFIL do arquivo .env na raiz do projeto.
"""

import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

try:
    from dotenv import load_dotenv
    import oracledb  # noqa: F401
except ImportError:
    print("Dependencias ausentes. Rode: pip install -r requirements.txt")
    sys.exit(1)

load_dotenv(RAIZ / ".env")
faltando = [v for v in ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN", "ORACLE_WALLET_DIR", "ORACLE_WALLET_PASSWORD") if not os.environ.get(v)]
if faltando:
    print("Faltam no .env:", ", ".join(faltando))
    sys.exit(1)

pasta = Path(os.environ["ORACLE_WALLET_DIR"])
for arquivo in ("tnsnames.ora", "ewallet.pem"):
    if not (pasta / arquivo).is_file():
        print(f"[FALHA] {arquivo} nao encontrado em {pasta}. Extraia o wallet (.zip) nessa pasta.")
        sys.exit(1)

perfil = os.environ.get("SELECT_AI_PERFIL", "PRAZO60_AI")


def etapa(nome, funcao):
    try:
        resultado = funcao()
        print(f"[OK]    {nome}: {resultado}")
        return resultado
    except Exception as erro:  # mensagem Oracle crua para diagnosticar, mas sem a chave do provedor
        print(f"[FALHA] {nome}: {re.sub(r'key=[^&\s]+', 'key=***', str(erro))}")
        sys.exit(1)


from server.oracle.database import query_one  # noqa: E402  (cria o pool com as variaveis acima)
from server.select_ai import perguntar  # noqa: E402

def perfil_existe():
    linha = query_one("SELECT profile_name FROM user_cloud_ai_profiles WHERE profile_name = :p", {"p": perfil})
    if not linha:
        raise RuntimeError(f"perfil {perfil} nao existe no schema de {os.environ['ORACLE_USER']} (rode a parte B do select_ai_usuario_app.sql)")
    return linha


etapa("Conexao", lambda: query_one("SELECT USER AS usuario, SYS_CONTEXT('USERENV', 'DB_NAME') AS banco FROM dual"))
etapa("Perfil no schema deste usuario", perfil_existe)
etapa("Acesso aos dados agregados (esperado 45416)", lambda: query_one("SELECT SUM(CASOS) AS casos FROM ADMIN.VW_P60_RESUMO_ANO"))
r = etapa("Select AI (showsql + narrate)", lambda: perguntar("Quantos casos ultrapassaram o prazo de 60 dias?", perfil))
print("\nSQL gerado:\n", r["sql_gerado"])
print("\nResposta:\n", r["resposta"])
print("\nTudo certo. Pode configurar as mesmas variaveis no Render e ligar SELECT_AI_HABILITADO=true.")
