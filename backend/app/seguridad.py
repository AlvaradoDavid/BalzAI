"""Hash de contraseñas, tokens JWT de administrador/superadministrador y claves de dispositivo.

Solo se usa la biblioteca estándar (PBKDF2) y PyJWT para mantener mínimas las dependencias.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt

from app.config import get_settings

ROL_ADMIN = "admin"
ROL_SUPERADMIN = "superadmin"
ROLES_PANEL = (ROL_ADMIN, ROL_SUPERADMIN)
ALGORITMO_JWT = "HS256"
ITERACIONES_PBKDF2 = 600_000  # recomendación OWASP para PBKDF2-HMAC-SHA256


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def hashear_clave(clave: str, iteraciones: int = ITERACIONES_PBKDF2) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${_b64(sal)}${_b64(derivada)}"


def verificar_clave(clave: str, clave_hash: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperado = clave_hash.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        derivada = hashlib.pbkdf2_hmac(
            "sha256", clave.encode("utf-8"), base64.b64decode(sal), int(iteraciones)
        )
    except ValueError:
        return False
    return hmac.compare_digest(derivada, base64.b64decode(esperado))


@lru_cache
def hash_ficticio() -> str:
    """Se verifica contra este hash cuando el usuario no existe, para que el tiempo
    de respuesta no revele qué nombres de usuario son válidos."""
    return hashear_clave(secrets.token_urlsafe(16))


def crear_token(administrador_id: int, rol: str = ROL_ADMIN) -> tuple[str, int]:
    """Devuelve el token y su vigencia en segundos."""
    ajustes = get_settings()
    vigencia = timedelta(minutes=ajustes.jwt_minutos_expiracion)
    ahora = datetime.now(timezone.utc)
    payload = {"sub": str(administrador_id), "rol": rol, "iat": ahora, "exp": ahora + vigencia}
    token = jwt.encode(payload, ajustes.jwt_secreto, algorithm=ALGORITMO_JWT)
    return token, int(vigencia.total_seconds())


def decodificar_token(token: str) -> dict:
    """Lanza jwt.InvalidTokenError si el token es inválido, está alterado o expiró."""
    return jwt.decode(
        token,
        get_settings().jwt_secreto,
        algorithms=[ALGORITMO_JWT],
        options={"require": ["sub", "rol", "exp"]},
    )


def generar_clave_dispositivo() -> str:
    return secrets.token_urlsafe(32)


def hash_clave_dispositivo(clave: str) -> str:
    # Las claves de dispositivo son aleatorias y largas: un SHA-256 basta y permite
    # buscarlas por índice. Las contraseñas humanas sí usan PBKDF2 (lento a propósito).
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()
