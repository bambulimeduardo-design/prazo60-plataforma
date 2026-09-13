"""Hash de senha (PBKDF2-SHA256, biblioteca padrao) e limitador de tentativas de login."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

ITERACOES_PADRAO = 600_000  # recomendacao OWASP (2023) para PBKDF2-SHA256


def gerar_hash(senha: str, iteracoes: int = ITERACOES_PADRAO) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, iteracoes)
    return "$".join(["pbkdf2_sha256", str(iteracoes), base64.b64encode(sal).decode(), base64.b64encode(derivada).decode()])


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        algoritmo, iteracoes, sal_b64, derivada_b64 = hash_armazenado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        sal = base64.b64decode(sal_b64)
        esperado = base64.b64decode(derivada_b64)
        iteracoes_int = int(iteracoes)
    except (ValueError, TypeError):
        # Mesmo com hash invalido, gastamos o mesmo tempo para nao revelar o motivo.
        hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), b"0" * 16, ITERACOES_PADRAO)
        return False
    calculado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, iteracoes_int)
    return hmac.compare_digest(calculado, esperado)


def textos_iguais(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class LimitadorTentativas:
    """Janela deslizante em memoria. Suficiente para uma instancia unica (plano do Render)."""

    def __init__(self, max_eventos: int, janela_segundos: int):
        self.max_eventos = max_eventos
        self.janela = janela_segundos
        self._eventos: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _podar(self, chave: str, agora: float) -> deque[float]:
        fila = self._eventos[chave]
        while fila and agora - fila[0] > self.janela:
            fila.popleft()
        return fila

    def segundos_bloqueado(self, chave: str) -> int:
        with self._lock:
            agora = time.monotonic()
            fila = self._podar(chave, agora)
            if len(fila) < self.max_eventos:
                return 0
            return max(1, int(self.janela - (agora - fila[0])))

    def registrar(self, chave: str) -> None:
        with self._lock:
            agora = time.monotonic()
            self._podar(chave, agora).append(agora)

    def limpar(self, chave: str | None = None) -> None:
        with self._lock:
            if chave is None:
                self._eventos.clear()
            else:
                self._eventos.pop(chave, None)
