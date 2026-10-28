"""Punto de entrada de la API.

Se eligió FastAPI por su rendimiento asíncrono, validación con Pydantic y documentación
OpenAPI automática (/docs), ideal para exponer la misma API a la web y a dispositivos.

Ejecutar:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.datos_ejemplo import cargar_datos_ejemplo
from app.routers import admin, auth, dispositivos, publico
from app.servicios.errores import ErrorNegocio


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    # MVP: las tablas se crean al arrancar. Al pasar a PostgreSQL en producción conviene
    # gestionar el esquema con migraciones (Alembic) a partir de app/models.py.
    Base.metadata.create_all(engine)
    ajustes = get_settings()
    if ajustes.cargar_datos_ejemplo:
        with SessionLocal() as db:
            cargar_datos_ejemplo(db, ajustes)
    yield


def crear_app() -> FastAPI:
    ajustes = get_settings()
    app = FastAPI(
        title="Parqueos Cuenca",
        description="Ocupación de parqueos calculada a partir de entradas y salidas de vehículos.",
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ajustes.cors_origenes,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Clave-Dispositivo"],
    )

    @app.exception_handler(ErrorNegocio)
    async def _error_negocio(_request: Request, error: ErrorNegocio) -> JSONResponse:
        return JSONResponse(status_code=error.codigo_http, content={"detail": error.mensaje})

    @app.get("/api/salud", tags=["Sistema"])
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    app.include_router(publico.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(dispositivos.router)
    return app


app = crear_app()
