"""Panel operativo de parqueaderos: registrar entradas/salidas y gestionar parqueos.

Accesible tanto para operadores/dueños de parqueadero (`rol = "admin"`) como para el
Administrador de la Aplicación (`rol = "superadmin"`). Si un operador tiene asignado un
`parqueo_id` específico, su visibilidad y acciones quedan acotadas a ese parqueadero.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencias import (
    AdminActual,
    DbSesion,
    requiere_admin,
    verificar_alcance_parqueo,
)
from app.esquemas import (
    DispositivoCreado,
    DispositivoCrear,
    MovimientoEntrada,
    ParqueoActualizar,
    ParqueoCrear,
    ParqueoSalida,
)
from app.models import Dispositivo, OrigenMovimiento, RolAdministrador
from app.seguridad import generar_clave_dispositivo, hash_clave_dispositivo
from app.servicios import ocupacion

router = APIRouter(
    prefix="/api/admin",
    tags=["Operación de Parqueaderos"],
    dependencies=[Depends(requiere_admin)],
)


@router.get("/parqueos", response_model=list[ParqueoSalida])
def listar_parqueos(db: DbSesion, administrador: AdminActual, ciudad: str | None = None):
    """Lista los parqueos (incluidos inactivos). Si el operador tiene un parqueo asignado,
    solo devuelve ese parqueadero."""
    filas = ocupacion.listar_parqueos(db, ciudad, incluir_inactivos=True)
    if (
        administrador.rol is not RolAdministrador.SUPERADMIN
        and administrador.parqueo_id is not None
    ):
        filas = [(p, o) for p, o in filas if p.id == administrador.parqueo_id]
    return [ParqueoSalida.desde(p, o) for p, o in filas]


@router.post("/parqueos", response_model=ParqueoSalida, status_code=status.HTTP_201_CREATED)
def crear_parqueo(datos: ParqueoCrear, db: DbSesion, administrador: AdminActual):
    if (
        administrador.rol is not RolAdministrador.SUPERADMIN
        and administrador.parqueo_id is not None
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Tu cuenta está asignada a un parqueadero específico y no puede dar de alta otros.",
        )
    return ParqueoSalida.desde(*ocupacion.crear_parqueo(db, datos.model_dump()))


@router.patch("/parqueos/{parqueo_id}", response_model=ParqueoSalida)
def actualizar_parqueo(
    parqueo_id: int, datos: ParqueoActualizar, db: DbSesion, administrador: AdminActual
):
    verificar_alcance_parqueo(administrador, parqueo_id)
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
    verificar_alcance_parqueo(administrador, parqueo_id)
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
def crear_dispositivo(
    parqueo_id: int, datos: DispositivoCrear, db: DbSesion, administrador: AdminActual
):
    """Da de alta un sensor de acceso para el parqueo y devuelve su clave (una sola vez)."""
    verificar_alcance_parqueo(administrador, parqueo_id)
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
