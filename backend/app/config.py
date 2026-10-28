"""Configuración leída de variables de entorno (o del archivo backend/.env)."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETO_JWT_DESARROLLO = "solo-para-desarrollo-cambiar-en-produccion"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    entorno: Literal["desarrollo", "produccion"] = "desarrollo"

    # SQLite para el MVP. Para PostgreSQL basta con cambiar la URL, p. ej.:
    # postgresql+psycopg://usuario:clave@localhost:5432/parqueos
    database_url: str = "sqlite:///./parqueos.db"

    jwt_secreto: str = SECRETO_JWT_DESARROLLO
    jwt_minutos_expiracion: int = 480

    # Orígenes del frontend autorizados por CORS (en desarrollo Vite usa un proxy y no lo necesita).
    cors_origenes: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Datos de ejemplo: ciudades, parqueos, un administrador y un dispositivo de prueba.
    # Solo se cargan si la base de datos está vacía.
    cargar_datos_ejemplo: bool = True
    admin_usuario: str = "admin"
    admin_clave: str = "parqueos2026"
    dispositivo_demo_clave: str = "sensor-demo-cuenca"

    @model_validator(mode="after")
    def _proteger_produccion(self) -> "Settings":
        if self.entorno == "produccion" and self.jwt_secreto == SECRETO_JWT_DESARROLLO:
            raise ValueError("En producción debes definir JWT_SECRETO con un valor propio.")
        if self.entorno == "produccion" and self.cargar_datos_ejemplo:
            raise ValueError("En producción define CARGAR_DATOS_EJEMPLO=false.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
