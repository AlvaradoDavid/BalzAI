"""Esquemas Pydantic: contratos de entrada y salida de la API."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import OrigenMovimiento, Parqueo, RolAdministrador, TipoMovimiento

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=2,
        max_length=60,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
Latitud = Annotated[float, Field(ge=-90, le=90)]
Longitud = Annotated[float, Field(ge=-180, le=180)]
Capacidad = Annotated[int, Field(gt=0, le=100_000)]
Zoom = Annotated[int, Field(ge=5, le=20)]


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


class CiudadCrear(BaseModel):
    slug: Slug
    nombre: Annotated[Texto, StringConstraints(max_length=120)]
    provincia: Annotated[Texto, StringConstraints(max_length=120)]
    latitud: Latitud
    longitud: Longitud
    zoom: Zoom = 14


class CiudadActualizar(BaseModel):
    nombre: Annotated[Texto, StringConstraints(max_length=120)] | None = None
    provincia: Annotated[Texto, StringConstraints(max_length=120)] | None = None
    latitud: Latitud | None = None
    longitud: Longitud | None = None
    zoom: Zoom | None = None


class DispositivoCrear(BaseModel):
    nombre: Annotated[Texto, StringConstraints(max_length=120)]


class DispositivoCreado(BaseModel):
    id: int
    nombre: str
    parqueo_id: int
    clave: str = Field(description="Se muestra UNA sola vez; guárdala en el dispositivo.")


class DispositivoSalida(BaseModel):
    id: int
    nombre: str
    parqueo_id: int
    parqueo_nombre: str
    activo: bool
    movimientos_registrados: int
    creado_en: datetime


class DispositivoActualizar(BaseModel):
    nombre: Annotated[Texto, StringConstraints(max_length=120)] | None = None
    activo: bool | None = None


# --------------------------------------------------------------------------- autenticación y cuentas


class LoginEntrada(BaseModel):
    usuario: Texto
    clave: Annotated[str, StringConstraints(min_length=1)]


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en: int = Field(description="Segundos de vigencia del token.")
    rol: RolAdministrador = RolAdministrador.ADMIN
    usuario: str = ""
    nombre: str | None = None
    parqueo_id: int | None = None


class PerfilSalida(BaseModel):
    id: int
    usuario: str
    nombre: str | None
    rol: RolAdministrador
    parqueo_id: int | None
    activo: bool


class OperadorCrear(BaseModel):
    usuario: Annotated[Texto, StringConstraints(max_length=60)]
    nombre: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=120)] = None
    clave: Annotated[str, StringConstraints(min_length=6, max_length=128)]
    rol: RolAdministrador = RolAdministrador.ADMIN
    parqueo_id: int | None = None


class OperadorActualizar(BaseModel):
    nombre: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=120)] = None
    clave: Annotated[str, StringConstraints(min_length=6, max_length=128)] | None = None
    rol: RolAdministrador | None = None
    parqueo_id: int | None = None
    activo: bool | None = None


class OperadorSalida(BaseModel):
    id: int
    usuario: str
    nombre: str | None
    rol: RolAdministrador
    parqueo_id: int | None
    parqueo_nombre: str | None
    activo: bool
    movimientos_registrados: int
    creado_en: datetime


# --------------------------------------------------------------------------- analíticas y tráfico


class DesgloseOrigen(BaseModel):
    manual: int
    dispositivo: int


class HoraPico(BaseModel):
    hora: str | None
    movimientos: int


class ResumenAnaliticas(BaseModel):
    ciudades_total: int
    parqueos_activos: int
    parqueos_inactivos: int
    capacidad_total: int
    ocupados_actuales: int
    disponibles_actuales: int
    porcentaje_ocupacion: float
    movimientos_totales: int
    entradas_totales: int
    salidas_totales: int
    movimientos_ventana: int
    entradas_ventana: int
    salidas_ventana: int
    por_origen: DesgloseOrigen
    hora_pico: HoraPico
    operadores_activos: int
    dispositivos_activos: int


class PuntoFlujoHorario(BaseModel):
    hora_iso: str
    etiqueta: str
    entradas: int
    salidas: int
    flujo_neto: int
    total: int


class TraficoParqueo(BaseModel):
    id: int
    nombre: str
    ciudad_id: int
    ciudad_nombre: str
    activo: bool
    capacidad: int
    ocupados: int
    disponibles: int
    porcentaje_ocupacion: float
    entradas_totales: int
    salidas_totales: int
    movimientos_ventana: int
    indice_rotacion: float
    dispositivos_activos: int
    operadores_asignados: int


class MovimientoRecienteSalida(BaseModel):
    id: int
    parqueo_id: int
    parqueo_nombre: str
    tipo: TipoMovimiento
    origen: OrigenMovimiento
    actor: str
    creado_en: datetime


class AnaliticasSalida(BaseModel):
    ventana_horas: int
    ciudad_filtro: str | None
    resumen: ResumenAnaliticas
    flujo_horario: list[PuntoFlujoHorario]
    trafico_por_parqueo: list[TraficoParqueo]
    movimientos_recientes: list[MovimientoRecienteSalida]
