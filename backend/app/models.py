"""Modelos de datos.

La ocupación de un parqueo NO se guarda en ninguna columna: se calcula siempre a
partir de la tabla `movimientos` (entradas − salidas). Ver app/servicios/ocupacion.py.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Los movimientos crecen sin límite: BIGINT en PostgreSQL. En SQLite debe ser
# INTEGER para que la columna sea alias del ROWID y se autoincremente.
IdGrande = BigInteger().with_variant(Integer(), "sqlite")


class TipoMovimiento(str, enum.Enum):
    ENTRADA = "entrada"
    SALIDA = "salida"


class OrigenMovimiento(str, enum.Enum):
    MANUAL = "manual"  # registrado por un administrador desde el panel
    DISPOSITIVO = "dispositivo"  # enviado por un sensor o barrera de acceso


def _enum_texto(tipo: type[enum.Enum], nombre: str) -> Enum:
    """Enum guardado como texto + CHECK, portable entre SQLite y PostgreSQL."""
    return Enum(
        tipo,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        length=12,
        values_callable=lambda miembros: [m.value for m in miembros],
    )


class Ciudad(Base):
    """Agregar una ciudad es insertar una fila: el frontend se centra con estos datos."""

    __tablename__ = "ciudades"
    __table_args__ = (
        CheckConstraint("latitud BETWEEN -90 AND 90", name="ck_ciudades_latitud"),
        CheckConstraint("longitud BETWEEN -180 AND 180", name="ck_ciudades_longitud"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    provincia: Mapped[str] = mapped_column(String(120))
    latitud: Mapped[float] = mapped_column(Float)
    longitud: Mapped[float] = mapped_column(Float)
    zoom: Mapped[int] = mapped_column(Integer, default=14)

    parqueos: Mapped[list["Parqueo"]] = relationship(back_populates="ciudad")


class Parqueo(Base):
    __tablename__ = "parqueos"
    __table_args__ = (
        UniqueConstraint("ciudad_id", "nombre", name="uq_parqueos_ciudad_nombre"),
        CheckConstraint("capacidad > 0", name="ck_parqueos_capacidad_positiva"),
        CheckConstraint("latitud BETWEEN -90 AND 90", name="ck_parqueos_latitud"),
        CheckConstraint("longitud BETWEEN -180 AND 180", name="ck_parqueos_longitud"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ciudad_id: Mapped[int] = mapped_column(ForeignKey("ciudades.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    direccion: Mapped[str | None] = mapped_column(String(255))
    latitud: Mapped[float] = mapped_column(Float)
    longitud: Mapped[float] = mapped_column(Float)
    capacidad: Mapped[int] = mapped_column(Integer)
    # Un parqueo inactivo deja de mostrarse en el mapa y no acepta movimientos,
    # pero conserva su historial (no se borra).
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ciudad: Mapped[Ciudad] = relationship(back_populates="parqueos")


class Movimiento(Base):
    """Cada fila es una entrada o una salida de un vehículo (sin ubicación interna)."""

    __tablename__ = "movimientos"
    __table_args__ = (
        # Permite calcular la ocupación de un parqueo leyendo solo el índice.
        Index("ix_movimientos_parqueo_tipo", "parqueo_id", "tipo"),
    )

    id: Mapped[int] = mapped_column(IdGrande, primary_key=True)
    parqueo_id: Mapped[int] = mapped_column(ForeignKey("parqueos.id"))
    tipo: Mapped[TipoMovimiento] = mapped_column(_enum_texto(TipoMovimiento, "tipo_movimiento"))
    origen: Mapped[OrigenMovimiento] = mapped_column(_enum_texto(OrigenMovimiento, "origen_movimiento"))
    # Trazabilidad: quién registró el movimiento (uno de los dos, según el origen).
    administrador_id: Mapped[int | None] = mapped_column(ForeignKey("administradores.id"))
    dispositivo_id: Mapped[int | None] = mapped_column(ForeignKey("dispositivos.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Administrador(Base):
    """Único rol con cuenta. Los usuarios de lectura son anónimos."""

    __tablename__ = "administradores"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(60), unique=True)
    clave_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dispositivo(Base):
    """Sensor o barrera de acceso. Su clave solo permite registrar movimientos de SU parqueo."""

    __tablename__ = "dispositivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    parqueo_id: Mapped[int] = mapped_column(ForeignKey("parqueos.id"), index=True)
    # SHA-256 de la clave; la clave en claro se muestra una sola vez al crearla.
    clave_hash: Mapped[str] = mapped_column(String(64), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
