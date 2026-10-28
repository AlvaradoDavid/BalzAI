"""Dependencias de FastAPI para el control de acceso.

- Lectura (mapa): pública, sin dependencia.
- Administrador: token JWT con rol "admin" en la cabecera `Authorization: Bearer <token>`.
- Dispositivo: clave propia en la cabecera `X-Clave-Dispositivo`; solo puede registrar
  movimientos del parqueo al que está asociado.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Administrador, Dispositivo
from app.seguridad import ROL_ADMIN, decodificar_token, hash_clave_dispositivo

DbSesion = Annotated[Session, Depends(get_db)]

# auto_error=False para devolver nuestros propios mensajes (401 en lugar de 403 de FastAPI).
_esquema_bearer = HTTPBearer(auto_error=False, description="Token obtenido en /api/auth/login")
_esquema_dispositivo = APIKeyHeader(
    name="X-Clave-Dispositivo", auto_error=False, description="Clave del sensor de acceso"
)


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def requiere_admin(
    db: DbSesion,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Security(_esquema_bearer)],
) -> Administrador:
    if credenciales is None:
        raise _no_autenticado("Se requiere iniciar sesión como administrador.")
    try:
        payload = decodificar_token(credenciales.credentials)
        administrador_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise _no_autenticado("Token inválido o expirado.") from None

    if payload.get("rol") != ROL_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Se requiere rol de administrador.")

    # Se consulta la base para que desactivar un administrador surta efecto de inmediato.
    administrador = db.get(Administrador, administrador_id)
    if administrador is None or not administrador.activo:
        raise _no_autenticado("El administrador no existe o está inactivo.")
    return administrador


def requiere_dispositivo(
    db: DbSesion,
    clave: Annotated[str | None, Security(_esquema_dispositivo)],
) -> Dispositivo:
    if not clave:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta la cabecera X-Clave-Dispositivo.")
    dispositivo = db.scalar(
        select(Dispositivo).where(Dispositivo.clave_hash == hash_clave_dispositivo(clave))
    )
    if dispositivo is None or not dispositivo.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clave de dispositivo inválida o inactiva.")
    return dispositivo


AdminActual = Annotated[Administrador, Depends(requiere_admin)]
DispositivoActual = Annotated[Dispositivo, Depends(requiere_dispositivo)]
