"""Endpoint para sensores y barreras de acceso.

El dispositivo se autentica con su clave (cabecera `X-Clave-Dispositivo`) y el parqueo
se deduce de esa clave: un sensor no puede alterar la ocupación de otro parqueo.
Se aplican exactamente las mismas validaciones de capacidad que en el registro manual.
"""

from fastapi import APIRouter, status

from app.dependencias import DbSesion, DispositivoActual
from app.esquemas import MovimientoEntrada, ParqueoSalida
from app.models import OrigenMovimiento
from app.servicios import ocupacion

router = APIRouter(prefix="/api/dispositivos", tags=["Dispositivos"])


@router.post("/movimientos", response_model=ParqueoSalida, status_code=status.HTTP_201_CREATED)
def registrar_movimiento(datos: MovimientoEntrada, db: DbSesion, dispositivo: DispositivoActual):
    parqueo, ocupados = ocupacion.registrar_movimiento(
        db,
        dispositivo.parqueo_id,
        datos.tipo,
        OrigenMovimiento.DISPOSITIVO,
        dispositivo_id=dispositivo.id,
    )
    return ParqueoSalida.desde(parqueo, ocupados)
