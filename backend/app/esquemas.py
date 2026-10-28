"""Esquemas Pydantic: contratos de entrada y salida de la API."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import Parqueo, TipoMovimiento

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Latitud = Annotated[float, Field(ge=-90, le=90)]
Longitud = Annotated[float, Field(ge=-180, le=180)]
Capacidad = Annotated[int, Field(gt=0, le=100_000)]


# --------------------------------------------------------------------------- lectura


class CiudadSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nombre: str
    provincia: str
    latitud: float
    longitud: float
    zoom: int


class ParqueoSalida(BaseModel):
    id: int
    ciudad_id: int
    nombre: str
    direccion: str | None
    latitud: float
    longitud: float
    capacidad: int
    ocupados: int
    disponibles: int
    activo: bool

    @classmethod
    def desde(cls, parqueo: Parqueo, ocupados: int) -> "ParqueoSalida":
        """Combina el parqueo con su ocupación calculada (no almacenada)."""
        return cls(
            id=parqueo.id,
            ciudad_id=parqueo.ciudad_id,
            nombre=parqueo.nombre,
            direccion=parqueo.direccion,
            latitud=parqueo.latitud,
            longitud=parqueo.longitud,
            capacidad=parqueo.capacidad,
            ocupados=ocupados,
            disponibles=parqueo.capacidad - ocupados,
            activo=parqueo.activo,
        )


# --------------------------------------------------------------------------- escritura


class MovimientoEntrada(BaseModel):
    tipo: TipoMovimiento = Field(description="'entrada' o 'salida'")


class ParqueoCrear(BaseModel):
    ciudad_id: int
    nombre: Annotated[Texto, StringConstraints(max_length=150)]
    direccion: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=255)] = None
    latitud: Latitud
    longitud: Longitud
    capacidad: Capacidad


class ParqueoActualizar(BaseModel):
    """Todos los campos son opcionales: solo se cambian los enviados."""

    nombre: Annotated[Texto, StringConstraints(max_length=150)] | None = None
    direccion: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=255)] = None
    latitud: Latitud | None = None
    longitud: Longitud | None = None
    capacidad: Capacidad | None = None
    activo: bool | None = None


class DispositivoCrear(BaseModel):
    nombre: Annotated[Texto, StringConstraints(max_length=120)]


class DispositivoCreado(BaseModel):
    id: int
    nombre: str
    parqueo_id: int
    clave: str = Field(description="Se muestra UNA sola vez; guárdala en el dispositivo.")


# --------------------------------------------------------------------------- autenticación


class LoginEntrada(BaseModel):
    usuario: Texto
    clave: Annotated[str, StringConstraints(min_length=1)]


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en: int = Field(description="Segundos de vigencia del token.")
