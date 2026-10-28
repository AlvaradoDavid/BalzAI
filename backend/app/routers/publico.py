"""Endpoints públicos de solo lectura: los usa el mapa."""

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.dependencias import DbSesion
from app.esquemas import CiudadSalida, ParqueoSalida
from app.models import Ciudad
from app.servicios import ocupacion
from app.servicios.errores import NoEncontrado

router = APIRouter(prefix="/api", tags=["Público"])


@router.get("/ciudades", response_model=list[CiudadSalida])
def listar_ciudades(db: DbSesion):
    """Ciudades disponibles, con el centro y zoom inicial del mapa."""
    return db.scalars(select(Ciudad).order_by(Ciudad.nombre)).all()


@router.get("/parqueos", response_model=list[ParqueoSalida])
def listar_parqueos(
    db: DbSesion,
    ciudad: str | None = Query(None, description="Slug de la ciudad, p. ej. 'cuenca'"),
):
    """Parqueos activos con su ocupación actual (opcionalmente filtrados por ciudad)."""
    return [ParqueoSalida.desde(p, o) for p, o in ocupacion.listar_parqueos(db, ciudad)]


@router.get("/parqueos/{parqueo_id}", response_model=ParqueoSalida)
def detalle_parqueo(parqueo_id: int, db: DbSesion):
    """Espacios disponibles y ocupados de un parqueo."""
    parqueo, ocupados = ocupacion.obtener_parqueo(db, parqueo_id)
    if not parqueo.activo:  # los inactivos no son visibles para el público
        raise NoEncontrado(f"No existe el parqueo {parqueo_id}.")
    return ParqueoSalida.desde(parqueo, ocupados)
