"""
Gera o hash PBKDF2 de uma senha para a variavel APP_PASSWORD_HASH.

Uso:
    python scripts/gerar_hash_senha.py            (pede a senha sem exibir)
    python scripts/gerar_hash_senha.py MINHA_SENHA
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.auth import gerar_hash  # noqa: E402

senha = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Senha: ")
print(gerar_hash(senha))
