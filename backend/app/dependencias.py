"""Dependencias de FastAPI para el control de acceso por rol (RBAC).

- Lectura (mapa): pública, sin dependencia.
- Administrador de parqueadero / Operador (`rol = "admin"`): dueño de parqueadero o personal de
  seguridad. Si tiene `parqueo_id` asignado, solo puede operar su parqueadero.
- Administrador de la aplicación (`rol = "superadmin"`): perfil jerárquicamente superior; tiene
  acceso completo a `/api/admin` y exclusivo a `/api/superadmin` (analíticas, flujo, tráfico,
  ciudades, operadores y sensores).
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
from app.models import Administrador, Dispositivo, RolAdministrador
from app.seguridad import ROLES_PANEL, ROL_SUPERADMIN, decodificar_token, hash_clave_dispositivo

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
    """Permite acceso a operadores de parqueadero (`admin`) y al `superadmin`."""
    if credenciales is None:
        raise _no_autenticado("Se requiere iniciar sesión como administrador.")
    try:
        payload = decodificar_token(credenciales.credentials)
        administrador_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise _no_autenticado("Token inválido o expirado.") from None

    if payload.get("rol") not in ROLES_PANEL:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Se requiere rol de administrador.")

    # Se consulta la base para que desactivar un administrador surta efecto de inmediato.
    administrador = db.get(Administrador, administrador_id)
    if administrador is None or not administrador.activo:
        raise _no_autenticado("El administrador no existe o está inactivo.")
    return administrador


def requiere_superadmin(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Security(_esquema_bearer)],
    administrador: Annotated[Administrador, Depends(requiere_admin)],
) -> Administrador:
    """Exige el perfil superior de Administrador de la Aplicación (`superadmin`)."""
    payload = decodificar_token(credenciales.credentials)
    if (
        payload.get("rol") != ROL_SUPERADMIN
        or administrador.rol is not RolAdministrador.SUPERADMIN
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Se requiere perfil de Superadministrador de la aplicación.",
        )
    return administrador


def verificar_alcance_parqueo(administrador: Administrador, parqueo_id: int) -> None:
    """Si un operador de parqueadero está asignado a un único parqueo, impide tocar otros."""
    if (
        administrador.rol is not RolAdministrador.SUPERADMIN
        and administrador.parqueo_id is not None
        and administrador.parqueo_id != parqueo_id
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Tu cuenta solo está autorizada para operar su parqueadero asignado.",
        )


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
SuperAdminActual = Annotated[Administrador, Depends(requiere_superadmin)]
DispositivoActual = Annotated[Dispositivo, Depends(requiere_dispositivo)]
