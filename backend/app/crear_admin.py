"""Crea (o restablece la contraseña de) un administrador desde la terminal.

Uso:  python -m app.crear_admin <usuario>

Pensado para producción, donde CARGAR_DATOS_EJEMPLO=false y no existe el admin de prueba.
"""

import sys
from getpass import getpass

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Administrador
from app.seguridad import hashear_clave


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m app.crear_admin <usuario>")
    usuario = sys.argv[1].strip()

    clave = getpass("Contraseña: ")
    if len(clave) < 8:
        sys.exit("La contraseña debe tener al menos 8 caracteres.")
    if clave != getpass("Repite la contraseña: "):
        sys.exit("Las contraseñas no coinciden.")

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        administrador = db.scalar(select(Administrador).where(Administrador.usuario == usuario))
        if administrador is None:
            db.add(Administrador(usuario=usuario, clave_hash=hashear_clave(clave)))
            print(f"Administrador '{usuario}' creado.")
        else:
            administrador.clave_hash = hashear_clave(clave)
            administrador.activo = True
            print(f"Contraseña de '{usuario}' actualizada.")
        db.commit()


if __name__ == "__main__":
    main()
