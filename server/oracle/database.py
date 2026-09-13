"""
Conexao ao Oracle Autonomous Database (Prazo60DB).

Nunca coloque usuario, senha ou caminho do wallet direto no codigo.
Tudo vem de variaveis de ambiente (arquivo .env, nao versionado no git).
"""

import os
import oracledb
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.environ["ORACLE_USER"]
DB_PASSWORD = os.environ["ORACLE_PASSWORD"]
DB_DSN = os.environ["ORACLE_DSN"]  # ex: prazo60db_medium, do tnsnames.ora do wallet
WALLET_DIR = os.environ["ORACLE_WALLET_DIR"]  # pasta onde o wallet foi extraido

# python-oracledb em modo thin suporta wallet (mTLS) direto, sem precisar
# instalar o Oracle Instant Client.
pool = oracledb.create_pool(
    user=DB_USER,
    password=DB_PASSWORD,
    dsn=DB_DSN,
    config_dir=WALLET_DIR,
    wallet_location=WALLET_DIR,
    wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD"),  # so se o wallet tiver senha propria
    min=1,
    max=4,
    increment=1,
)


@contextmanager
def get_connection():
    conn = pool.acquire()
    try:
        yield conn
    finally:
        pool.release(conn)


def query_all(sql: str, params: dict | None = None) -> list[dict]:
    """Executa uma query e devolve lista de dicionarios (nome da coluna -> valor)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or {})
        colunas = [c[0].lower() for c in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def query_one(sql: str, params: dict | None = None) -> dict | None:
    resultado = query_all(sql, params)
    return resultado[0] if resultado else None
