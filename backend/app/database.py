"""Conexión a la base de datos. El mismo código funciona con SQLite y PostgreSQL."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def crear_engine(url: str, **opciones) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True, **opciones)

    # SQLite: se permite usar la conexión desde los hilos de FastAPI y se espera
    # hasta 15 s cuando otra escritura tiene la base bloqueada.
    opciones.setdefault("connect_args", {"check_same_thread": False, "timeout": 15})
    engine = create_engine(url, **opciones)

    @event.listens_for(engine, "connect")
    def _activar_claves_foraneas(conexion_dbapi, _registro):
        # SQLite no valida claves foráneas salvo que se active por conexión.
        cursor = conexion_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = crear_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
