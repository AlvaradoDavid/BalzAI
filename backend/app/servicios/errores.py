"""Errores de negocio. main.py los traduce a respuestas HTTP."""


class ErrorNegocio(Exception):
    codigo_http = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontrado(ErrorNegocio):
    codigo_http = 404


class Conflicto(ErrorNegocio):
    """La operación contradice el estado actual (parqueo lleno, vacío, nombre repetido...)."""

    codigo_http = 409
