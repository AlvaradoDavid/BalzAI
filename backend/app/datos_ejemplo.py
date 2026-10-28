"""Carga inicial de datos de ejemplo (solo si la base está vacía).

Los datos viven en app/datos/datos_ejemplo.json: para sumar ciudades o parqueos basta
con editar ese archivo (o insertar filas directamente en la base).
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    Administrador,
    Ciudad,
    Dispositivo,
    Movimiento,
    OrigenMovimiento,
    Parqueo,
    TipoMovimiento,
)
from app.seguridad import hash_clave_dispositivo, hashear_clave

ARCHIVO_DATOS = Path(__file__).parent / "datos" / "datos_ejemplo.json"


def cargar_datos_ejemplo(db: Session, ajustes: Settings, archivo: Path = ARCHIVO_DATOS) -> bool:
    """Inserta ciudades, parqueos, un administrador y un dispositivo de prueba.

    Devuelve False (sin tocar nada) si ya existen ciudades en la base.
    """
    if db.scalar(select(Ciudad.id).limit(1)) is not None:
        return False

    administrador = db.scalar(select(Administrador).where(Administrador.usuario == ajustes.admin_usuario))
    if administrador is None:
        administrador = Administrador(
            usuario=ajustes.admin_usuario, clave_hash=hashear_clave(ajustes.admin_clave)
        )
        db.add(administrador)
        db.flush()

    datos = json.loads(archivo.read_text(encoding="utf-8"))
    primer_parqueo: Parqueo | None = None

    for datos_ciudad in datos["ciudades"]:
        datos_parqueos = datos_ciudad.pop("parqueos", [])
        ciudad = Ciudad(**datos_ciudad)
        db.add(ciudad)
        db.flush()

        for datos_parqueo in datos_parqueos:
            ocupados = int(datos_parqueo.pop("ocupados_iniciales", 0))
            parqueo = Parqueo(ciudad_id=ciudad.id, **datos_parqueo)
            if not 0 <= ocupados <= parqueo.capacidad:
                raise ValueError(f"'ocupados_iniciales' fuera de rango en {parqueo.nombre}.")
            db.add(parqueo)
            db.flush()
            primer_parqueo = primer_parqueo or parqueo

            # La ocupación inicial se representa con movimientos de entrada, igual que
            # en la operación normal: no existe un contador almacenado que inicializar.
            db.add_all(
                Movimiento(
                    parqueo_id=parqueo.id,
                    tipo=TipoMovimiento.ENTRADA,
                    origen=OrigenMovimiento.MANUAL,
                    administrador_id=administrador.id,
                )
                for _ in range(ocupados)
            )

    if primer_parqueo is not None and ajustes.dispositivo_demo_clave:
        db.add(
            Dispositivo(
                nombre="Sensor de demostración",
                parqueo_id=primer_parqueo.id,
                clave_hash=hash_clave_dispositivo(ajustes.dispositivo_demo_clave),
            )
        )

    db.commit()
    return True
