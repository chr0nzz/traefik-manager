import os

from cryptography.fernet import Fernet, InvalidToken

from core import env
from core.env import logger


def get_otp_fernet() -> Fernet:
    key = os.environ.get('OTP_ENCRYPTION_KEY', '').strip()
    if not key:
        if os.path.exists(env.OTP_KEY_PATH):
            with open(env.OTP_KEY_PATH) as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key().decode()
            os.makedirs(os.path.dirname(env.OTP_KEY_PATH), exist_ok=True)
            # This key decrypts every stored secret, so it must not be readable by other users
            # on the host or by another container sharing the config volume. Create it with the
            # mode already set rather than writing it world-readable and fixing it afterwards.
            fd = os.open(env.OTP_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(key)
            logger.warning(
                "Generated a new secret encryption key at %s. Any secret stored with an earlier "
                "key - the two-factor secret, the OIDC client secret, the git backup token - "
                "can no longer be read and has to be entered again.", env.OTP_KEY_PATH)
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(secret: str) -> str:
    if not secret:
        return ''
    return get_otp_fernet().encrypt(secret.encode()).decode()


FERNET_PREFIX = 'gAAAAA'
_plaintext_count = 0


def looks_encrypted(value: str) -> bool:
    return isinstance(value, str) and value.startswith(FERNET_PREFIX)


def plaintext_secrets_seen() -> bool:
    return _plaintext_count > 0


def clear_plaintext_seen():
    global _plaintext_count
    _plaintext_count = 0


def decrypt_secret(token: str) -> str:
    if not token:
        return ''
    if not looks_encrypted(token):
        global _plaintext_count
        _plaintext_count += 1
        return token
    try:
        return get_otp_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        logger.error("Failed to decrypt a stored secret - the encryption key does not match the "
                     "one it was stored with. Anything relying on that secret, including "
                     "two-factor sign-in, will behave as if it was never set. Restore %s or "
                     "OTP_ENCRYPTION_KEY, or set the secret again.", env.OTP_KEY_PATH)
        return ''
