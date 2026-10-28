"""Consola de Superadministración de la aplicación.

Exclusivo para el rol `superadmin`:
- Analíticas globales, flujo horario de entradas/salidas, rotación y tráfico en tiempo real.
- Gestión de ciudades para escalar la aplicación al resto del país.
- Gestión de cuentas de dueños de parqueaderos / personal de seguridad (operadores).
- Gestión global de sensores y dispositivos IoT.
"""

from fastapi import APIRouter, Depends, Query, status

from app.dependencias import DbSesion, SuperAdminActual, requiere_superadmin
from app.esquemas import (
    AnaliticasSalida,
    CiudadActualizar,
    CiudadCrear,
    CiudadSalida,
    DispositivoActualizar,
    DispositivoSalida,
    OperadorActualizar,
    OperadorCrear,
    OperadorSalida,
)
from app.servicios import analiticas

router = APIRouter(
    prefix="/api/superadmin",
    tags=["Superadministración y Analíticas"],
    dependencies=[Depends(requiere_superadmin)],
)


@router.get("/analiticas", response_model=AnaliticasSalida)
def obtener_analiticas(
    db: DbSesion,
    ciudad: str | None = Query(None, description="Filtrar por slug de ciudad, p. ej. 'cuenca'"),
    horas: int = Query(24, ge=1, le=168, description="Ventana de análisis en horas (1 a 168)"),
):
    """Métricas globales de la plataforma, flujo horario (entradas vs. salidas),
    saturación/rotación por parqueadero y bitácora de tráfico en vivo."""
    return analiticas.obtener_analiticas(db, ciudad_slug=ciudad, ventana_horas=horas)


@router.post("/ciudades", response_model=CiudadSalida, status_code=status.HTTP_201_CREATED)
def crear_ciudad(datos: CiudadCrear, db: DbSesion):
    """Agrega una nueva ciudad a la aplicación."""
    return analiticas.crear_ciudad(db, datos.model_dump())


@router.patch("/ciudades/{ciudad_id}", response_model=CiudadSalida)
def actualizar_ciudad(ciudad_id: int, datos: CiudadActualizar, db: DbSesion):
    return analiticas.actualizar_ciudad(db, ciudad_id, datos.model_dump(exclude_unset=True))


@router.get("/operadores", response_model=list[OperadorSalida])
def listar_operadores(db: DbSesion):
    """Lista todas las cuentas de superadministradores y operadores/dueños de parqueaderos."""
    return analiticas.listar_operadores(db)


@router.post("/operadores", response_model=OperadorSalida, status_code=status.HTTP_201_CREATED)
def crear_operador(datos: OperadorCrear, db: DbSesion):
    """Crea una cuenta para un dueño de parqueadero, guardia de seguridad o superadministrador."""
    return analiticas.crear_operador(db, datos.model_dump())


@router.patch("/operadores/{operador_id}", response_model=OperadorSalida)
def actualizar_operador(
    operador_id: int,
    datos: OperadorActualizar,
    db: DbSesion,
    superadmin: SuperAdminActual,
):
    cambios = datos.model_dump(exclude_unset=True)
    return analiticas.actualizar_operador(db, operador_id, cambios, superadmin.id)


@router.get("/dispositivos", response_model=list[DispositivoSalida])
def listar_dispositivos(db: DbSesion):
    """Lista todos los sensores/barreras registrados en todos los parqueaderos."""
    return analiticas.listar_dispositivos(db)


@router.patch("/dispositivos/{dispositivo_id}", response_model=DispositivoSalida)
def actualizar_dispositivo(dispositivo_id: int, datos: DispositivoActualizar, db: DbSesion):
    return analiticas.actualizar_dispositivo(
        db, dispositivo_id, datos.model_dump(exclude_unset=True)
    )
