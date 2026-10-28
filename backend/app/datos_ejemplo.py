"""Carga inicial de datos de ejemplo (solo si la base está vacía).

Los datos viven en app/datos/datos_ejemplo.json: para sumar ciudades o parqueos basta
con editar ese archivo (o crearlos desde la consola de Superadministración).
"""

from datetime import datetime, timedelta, timezone
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
    RolAdministrador,
    TipoMovimiento,
)
from app.seguridad import hash_clave_dispositivo, hashear_clave

ARCHIVO_DATOS = Path(__file__).parent / "datos" / "datos_ejemplo.json"


def cargar_datos_ejemplo(db: Session, ajustes: Settings, archivo: Path = ARCHIVO_DATOS) -> bool:
    """Inserta ciudades, parqueos, superadmin, operadores y un dispositivo de prueba.

    Devuelve False (sin tocar nada) si ya existen ciudades en la base.
    """
    if db.scalar(select(Ciudad.id).limit(1)) is not None:
        return False

    # 1. Superadministrador de la aplicación (control global y analíticas).
    superadmin = db.scalar(
        select(Administrador).where(Administrador.usuario == ajustes.superadmin_usuario)
    )
    if superadmin is None:
        superadmin = Administrador(
            usuario=ajustes.superadmin_usuario,
            nombre="Dirección General BalzAI",
            clave_hash=hashear_clave(ajustes.superadmin_clave),
            rol=RolAdministrador.SUPERADMIN,
        )
        db.add(superadmin)
        db.flush()

    # 2. Administrador / Operador de parqueaderos (dueño o personal de seguridad).
    administrador = db.scalar(
        select(Administrador).where(Administrador.usuario == ajustes.admin_usuario)
    )
    if administrador is None:
        administrador = Administrador(
            usuario=ajustes.admin_usuario,
            nombre="Operador General de Parqueaderos",
            clave_hash=hashear_clave(ajustes.admin_clave),
            rol=RolAdministrador.ADMIN,
        )
        db.add(administrador)
        db.flush()

    datos = json.loads(archivo.read_text(encoding="utf-8"))
    primer_parqueo: Parqueo | None = None
    dispositivo_demo: Dispositivo | None = None
    ahora = datetime.now(timezone.utc)

    for datos_ciudad in datos["ciudades"]:
        datos_parqueos = datos_ciudad.pop("parqueos", [])
        ciudad = Ciudad(**datos_ciudad)
        db.add(ciudad)
        db.flush()

        for indice_parqueo, datos_parqueo in enumerate(datos_parqueos):
            ocupados = int(datos_parqueo.pop("ocupados_iniciales", 0))
            parqueo = Parqueo(ciudad_id=ciudad.id, **datos_parqueo)
            if not 0 <= ocupados <= parqueo.capacidad:
                raise ValueError(f"'ocupados_iniciales' fuera de rango en {parqueo.nombre}.")
            db.add(parqueo)
            db.flush()

            if primer_parqueo is None:
                primer_parqueo = parqueo
                if ajustes.dispositivo_demo_clave:
                    dispositivo_demo = Dispositivo(
                        nombre="Sensor Barrera Principal Calderón",
                        parqueo_id=primer_parqueo.id,
                        clave_hash=hash_clave_dispositivo(ajustes.dispositivo_demo_clave),
                    )
                    db.add(dispositivo_demo)
                    db.flush()

            # Para que la vista de flujo y tráfico muestre tanto entradas como salidas
            # en las últimas 12 horas sin alterar la ocupación final (`ocupados`),
            # registramos `ocupados + rotacion_extra` entradas y `rotacion_extra` salidas.
            rotacion_extra = min(12, max(4, ocupados // 8)) if ocupados > 0 else 0
            total_entradas = ocupados + rotacion_extra
            usar_sensor = dispositivo_demo is not None and parqueo.id == primer_parqueo.id

            movimientos_parqueo: list[Movimiento] = []
            for i in range(total_entradas):
                horas_atras = ((i * 7 + indice_parqueo * 3) % 12) + (i % 5) * 0.18
                instante = ahora - timedelta(hours=horas_atras)
                es_sensor = usar_sensor and (i % 3 == 0)
                movimientos_parqueo.append(
                    Movimiento(
                        parqueo_id=parqueo.id,
                        tipo=TipoMovimiento.ENTRADA,
                        origen=OrigenMovimiento.DISPOSITIVO if es_sensor else OrigenMovimiento.MANUAL,
                        administrador_id=None if es_sensor else administrador.id,
                        dispositivo_id=dispositivo_demo.id if es_sensor else None,
                        creado_en=instante,
                    )
                )

            for j in range(rotacion_extra):
                horas_atras = ((j * 5 + indice_parqueo * 2) % 10) + 0.1
                instante = ahora - timedelta(hours=horas_atras)
                es_sensor = usar_sensor and (j % 2 == 0)
                movimientos_parqueo.append(
                    Movimiento(
                        parqueo_id=parqueo.id,
                        tipo=TipoMovimiento.SALIDA,
                        origen=OrigenMovimiento.DISPOSITIVO if es_sensor else OrigenMovimiento.MANUAL,
                        administrador_id=None if es_sensor else administrador.id,
                        dispositivo_id=dispositivo_demo.id if es_sensor else None,
                        creado_en=instante,
                    )
                )

            db.add_all(movimientos_parqueo)

    # 3. Operador de ejemplo asignado exclusivamente al primer parqueadero (Parque Calderón).
    if primer_parqueo is not None:
        guardia = db.scalar(
            select(Administrador).where(Administrador.usuario == "guardia_calderon")
        )
        if guardia is None:
            db.add(
                Administrador(
                    usuario="guardia_calderon",
                    nombre="Seguridad Parque Calderón",
                    clave_hash=hashear_clave(ajustes.admin_clave),
                    rol=RolAdministrador.ADMIN,
                    parqueo_id=primer_parqueo.id,
                )
            )

    db.commit()
    return True
