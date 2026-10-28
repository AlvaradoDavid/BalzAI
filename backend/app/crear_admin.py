"""Crea (o restablece la contraseña de) un administrador o superadministrador desde la terminal.

Uso:
  python -m app.crear_admin <usuario> [admin|superadmin]

Pensado para producción, donde CARGAR_DATOS_EJEMPLO=false.
"""

import sys
from getpass import getpass

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Administrador, RolAdministrador
from app.seguridad import hashear_clave


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit("Uso: python -m app.crear_admin <usuario> [admin|superadmin]")
    usuario = sys.argv[1].strip()
    rol_arg = sys.argv[2].strip().lower() if len(sys.argv) == 3 else "superadmin"
    try:
        rol = RolAdministrador(rol_arg)
    except ValueError:
        sys.exit("El rol debe ser 'admin' o 'superadmin'.")

    clave = getpass("Contraseña: ")
    if len(clave) < 8:
        sys.exit("La contraseña debe tener al menos 8 caracteres.")
    if clave != getpass("Repite la contraseña: "):
        sys.exit("Las contraseñas no coinciden.")

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        administrador = db.scalar(select(Administrador).where(Administrador.usuario == usuario))
        if administrador is None:
            db.add(Administrador(usuario=usuario, clave_hash=hashear_clave(clave), rol=rol))
            print(f"Cuenta '{usuario}' ({rol.value}) creada.")
        else:
            administrador.clave_hash = hashear_clave(clave)
            administrador.rol = rol
            administrador.activo = True
            print(f"Cuenta '{usuario}' ({rol.value}) actualizada.")
        db.commit()


if __name__ == "__main__":
    main()
