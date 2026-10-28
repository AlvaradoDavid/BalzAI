"""Fixtures compartidas: cada prueba usa su propia base SQLite temporal."""

import os

# Debe definirse antes de importar la app: evita tocar la base real y los datos de ejemplo.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CARGAR_DATOS_EJEMPLO"] = "false"
os.environ["ENTORNO"] = "desarrollo"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base, crear_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Administrador, Ciudad, Dispositivo, Parqueo  # noqa: E402
from app.seguridad import crear_token, hash_clave_dispositivo, hashear_clave  # noqa: E402

CLAVE_ADMIN = "clave-de-prueba"
CLAVE_DISPOSITIVO = "clave-sensor-prueba"


@pytest.fixture
def fabrica_sesiones(tmp_path):
    """Base en archivo (no en memoria) para poder abrir varias conexiones concurrentes."""
    engine = crear_engine(f"sqlite:///{tmp_path / 'pruebas.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def db(fabrica_sesiones):
    with fabrica_sesiones() as sesion:
        yield sesion


@pytest.fixture
def datos(db):
    """Una ciudad, dos parqueos (capacidad 3 y 10), un administrador y un dispositivo."""
    ciudad = Ciudad(slug="cuenca", nombre="Cuenca", provincia="Azuay", latitud=-2.9, longitud=-79.0)
    db.add(ciudad)
    db.flush()
    pequeno = Parqueo(ciudad_id=ciudad.id, nombre="Pequeño", latitud=-2.89, longitud=-79.0, capacidad=3)
    grande = Parqueo(ciudad_id=ciudad.id, nombre="Grande", latitud=-2.91, longitud=-79.01, capacidad=10)
    # Pocas iteraciones de PBKDF2 para que las pruebas sean rápidas.
    admin = Administrador(usuario="admin", clave_hash=hashear_clave(CLAVE_ADMIN, iteraciones=1_000))
    db.add_all([pequeno, grande, admin])
    db.flush()
    sensor = Dispositivo(
        nombre="Sensor", parqueo_id=pequeno.id, clave_hash=hash_clave_dispositivo(CLAVE_DISPOSITIVO)
    )
    db.add(sensor)
    db.commit()
    return {"ciudad": ciudad, "pequeno": pequeno, "grande": grande, "admin": admin, "sensor": sensor}


@pytest.fixture
def cliente(fabrica_sesiones):
    def _get_db_pruebas():
        with fabrica_sesiones() as sesion:
            yield sesion

    app.dependency_overrides[get_db] = _get_db_pruebas
    # Sin "with": no se ejecuta el ciclo de vida (no se crean tablas en la base real).
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def cabeceras_admin(datos):
    token, _ = crear_token(datos["admin"].id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cabeceras_dispositivo():
    return {"X-Clave-Dispositivo": CLAVE_DISPOSITIVO}
