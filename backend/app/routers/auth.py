"""Inicio de sesión y consulta de perfil para operadores y superadministradores."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencias import AdminActual, DbSesion
from app.esquemas import LoginEntrada, PerfilSalida, TokenSalida
from app.models import Administrador
from app.seguridad import crear_token, hash_ficticio, verificar_clave

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenSalida)
def login(datos: LoginEntrada, db: DbSesion):
    administrador = db.scalar(select(Administrador).where(Administrador.usuario == datos.usuario))
    # Se verifica siempre un hash (real o ficticio) para no revelar qué usuarios existen.
    clave_valida = verificar_clave(
        datos.clave, administrador.clave_hash if administrador else hash_ficticio()
    )
    if administrador is None or not clave_valida or not administrador.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos.")
    token, expira_en = crear_token(administrador.id, rol=administrador.rol.value)
    return TokenSalida(
        access_token=token,
        expira_en=expira_en,
        rol=administrador.rol,
        usuario=administrador.usuario,
        nombre=administrador.nombre,
        parqueo_id=administrador.parqueo_id,
    )


@router.get("/perfil", response_model=PerfilSalida)
def obtener_perfil(administrador: AdminActual):
    """Devuelve los datos y el rol de la cuenta autenticada."""
    return PerfilSalida(
        id=administrador.id,
        usuario=administrador.usuario,
        nombre=administrador.nombre,
        rol=administrador.rol,
        parqueo_id=administrador.parqueo_id,
        activo=administrador.activo,
    )
