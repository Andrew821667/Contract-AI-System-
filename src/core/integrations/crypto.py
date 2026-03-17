"""
Шифрование секретов для интеграций (Fernet symmetric encryption).

Ключ берётся из SECRET_KEY приложения (через HKDF derivation).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger


def _derive_fernet_key(secret_key: str) -> bytes:
    """Детерминированно выводим 32-byte Fernet key из SECRET_KEY приложения."""
    digest = hashlib.sha256(secret_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    """Получить Fernet instance из настроек приложения."""
    from config.settings import settings
    key = _derive_fernet_key(settings.secret_key)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Зашифровать секрет. Возвращает base64-encoded ciphertext с префиксом 'enc:'."""
    if not plaintext or plaintext.startswith("enc:"):
        return plaintext  # уже зашифрован или пустой
    f = _get_fernet()
    token = f.encrypt(plaintext.encode())
    return "enc:" + token.decode()


def decrypt_secret(ciphertext: str) -> str:
    """Расшифровать секрет. Если не зашифрован (нет префикса 'enc:'), вернуть как есть."""
    if not ciphertext or not ciphertext.startswith("enc:"):
        return ciphertext  # plaintext (legacy) — вернуть как есть
    f = _get_fernet()
    try:
        token = ciphertext[4:].encode()  # убираем "enc:"
        return f.decrypt(token).decode()
    except InvalidToken:
        logger.error("Failed to decrypt webhook secret — invalid token or wrong key")
        return ""
