"""Panel de administración mínimo: registrar entradas/salidas y gestionar parqueos.

Todas las rutas de este módulo exigen un token de administrador.
"""

from fastapi import APIRouter, Depends, status

from app.dependencias import AdminActual, DbSesion, requiere_admin
from app.esquemas import (
    DispositivoCreado,
    DispositivoCrear,
    MovimientoEntrada,
    ParqueoActualizar,
    ParqueoCrear,
    ParqueoSalida,
)
from app.models import Dispositivo, OrigenMovimiento
from app.seguridad import generar_clave_dispositivo, hash_clave_dispositivo
from app.servicios import ocupacion

router = APIRouter(
    prefix="/api/admin",
    tags=["Administración"],
    dependencies=[Depends(requiere_admin)],
)


@router.get("/parqueos", response_model=list[ParqueoSalida])
def listar_parqueos(db: DbSesion, ciudad: str | None = None):
    """Igual que el listado público, pero incluye los parqueos inactivos."""
    filas = ocupacion.listar_parqueos(db, ciudad, incluir_inactivos=True)
    return [ParqueoSalida.desde(p, o) for p, o in filas]


@router.post("/parqueos", response_model=ParqueoSalida, status_code=status.HTTP_201_CREATED)
def crear_parqueo(datos: ParqueoCrear, db: DbSesion):
    return ParqueoSalida.desde(*ocupacion.crear_parqueo(db, datos.model_dump()))


@router.patch("/parqueos/{parqueo_id}", response_model=ParqueoSalida)
def actualizar_parqueo(parqueo_id: int, datos: ParqueoActualizar, db: DbSesion):
    # Solo los campos enviados; `null` únicamente tiene sentido para borrar la dirección.
    cambios = {
        campo: valor
        for campo, valor in datos.model_dump(exclude_unset=True).items()
        if valor is not None or campo == "direccion"
    }
    return ParqueoSalida.desde(*ocupacion.actualizar_parqueo(db, parqueo_id, cambios))


@router.post(
    "/parqueos/{parqueo_id}/movimientos",
    response_model=ParqueoSalida,
    status_code=status.HTTP_201_CREATED,
)
def registrar_movimiento(
    parqueo_id: int, datos: MovimientoEntrada, db: DbSesion, administrador: AdminActual
):
    """Registro manual de una entrada o salida. Responde 409 si violaría la capacidad."""
    parqueo, ocupados = ocupacion.registrar_movimiento(
        db,
        parqueo_id,
        datos.tipo,
        OrigenMovimiento.MANUAL,
        administrador_id=administrador.id,
    )
    return ParqueoSalida.desde(parqueo, ocupados)


@router.post(
    "/parqueos/{parqueo_id}/dispositivos",
    response_model=DispositivoCreado,
    status_code=status.HTTP_201_CREATED,
)
def crear_dispositivo(parqueo_id: int, datos: DispositivoCrear, db: DbSesion):
    """Da de alta un sensor de acceso para el parqueo y devuelve su clave (una sola vez)."""
    ocupacion.obtener_parqueo(db, parqueo_id)  # 404 si no existe
    clave = generar_clave_dispositivo()
    dispositivo = Dispositivo(
        nombre=datos.nombre, parqueo_id=parqueo_id, clave_hash=hash_clave_dispositivo(clave)
    )
    db.add(dispositivo)
    db.commit()
    return DispositivoCreado(
        id=dispositivo.id, nombre=dispositivo.nombre, parqueo_id=parqueo_id, clave=clave
    )
