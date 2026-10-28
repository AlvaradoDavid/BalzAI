"""Control de acceso por rol y comportamiento de los endpoints HTTP."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import get_settings
from app.seguridad import ALGORITMO_JWT, crear_token
from tests.conftest import CLAVE_ADMIN


def url_movimiento(parqueo):
    return f"/api/admin/parqueos/{parqueo.id}/movimientos"


def contiene(respuesta: dict, **esperado) -> bool:
    """True si la respuesta incluye los pares clave/valor esperados."""
    return all(respuesta.get(clave) == valor for clave, valor in esperado.items())


# --------------------------------------------------------------------------- lectura pública


def test_listado_publico_sin_autenticacion(cliente, datos):
    respuesta = cliente.get("/api/parqueos", params={"ciudad": "cuenca"})
    assert respuesta.status_code == 200
    pequeno = next(p for p in respuesta.json() if p["nombre"] == "Pequeño")
    assert contiene(pequeno, capacidad=3, ocupados=0, disponibles=3)


def test_detalle_publico_muestra_disponibles_y_ocupados(cliente, datos, cabeceras_admin):
    cliente.post(url_movimiento(datos["grande"]), json={"tipo": "entrada"}, headers=cabeceras_admin)
    respuesta = cliente.get(f"/api/parqueos/{datos['grande'].id}")
    assert respuesta.status_code == 200
    assert contiene(respuesta.json(), ocupados=1, disponibles=9)


def test_ciudad_inexistente_devuelve_404(cliente, datos):
    assert cliente.get("/api/parqueos", params={"ciudad": "atlantida"}).status_code == 404


def test_parqueo_inactivo_no_es_visible_al_publico(cliente, datos, cabeceras_admin):
    pequeno = datos["pequeno"]
    cliente.patch(f"/api/admin/parqueos/{pequeno.id}", json={"activo": False}, headers=cabeceras_admin)

    nombres = [p["nombre"] for p in cliente.get("/api/parqueos").json()]
    assert "Pequeño" not in nombres
    assert cliente.get(f"/api/parqueos/{pequeno.id}").status_code == 404
    # El administrador sí lo sigue viendo para poder reactivarlo.
    nombres_admin = [p["nombre"] for p in cliente.get("/api/admin/parqueos", headers=cabeceras_admin).json()]
    assert "Pequeño" in nombres_admin


# --------------------------------------------------------------------------- administrador


def test_login_correcto_devuelve_token_utilizable(cliente, datos):
    respuesta = cliente.post("/api/auth/login", json={"usuario": "admin", "clave": CLAVE_ADMIN})
    assert respuesta.status_code == 200
    token = respuesta.json()["access_token"]
    privada = cliente.get("/api/admin/parqueos", headers={"Authorization": f"Bearer {token}"})
    assert privada.status_code == 200


@pytest.mark.parametrize("usuario, clave", [("admin", "incorrecta"), ("nadie", CLAVE_ADMIN)])
def test_login_incorrecto(cliente, datos, usuario, clave):
    respuesta = cliente.post("/api/auth/login", json={"usuario": usuario, "clave": clave})
    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "metodo, ruta, cuerpo",
    [
        ("get", "/api/admin/parqueos", None),
        ("post", "/api/admin/parqueos", {"ciudad_id": 1, "nombre": "X", "latitud": 0, "longitud": 0, "capacidad": 5}),
        ("patch", "/api/admin/parqueos/1", {"capacidad": 50}),
        ("post", "/api/admin/parqueos/1/movimientos", {"tipo": "entrada"}),
        ("post", "/api/admin/parqueos/1/dispositivos", {"nombre": "Sensor"}),
    ],
)
def test_rutas_de_escritura_exigen_administrador(cliente, datos, metodo, ruta, cuerpo):
    peticion = getattr(cliente, metodo)
    kwargs = {"json": cuerpo} if cuerpo is not None else {}
    assert peticion(ruta, **kwargs).status_code == 401
    assert peticion(ruta, headers={"Authorization": "Bearer basura"}, **kwargs).status_code == 401


def test_token_sin_rol_admin_es_rechazado(cliente, datos):
    token, _ = crear_token(datos["admin"].id, rol="lector")
    respuesta = cliente.post(
        url_movimiento(datos["pequeno"]), json={"tipo": "entrada"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


def test_token_expirado_es_rechazado(cliente, datos):
    vencido = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": str(datos["admin"].id), "rol": "admin", "exp": vencido},
        get_settings().jwt_secreto,
        algorithm=ALGORITMO_JWT,
    )
    respuesta = cliente.get("/api/admin/parqueos", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 401


def test_admin_registra_entrada_y_salida(cliente, datos, cabeceras_admin):
    url = url_movimiento(datos["pequeno"])
    assert cliente.post(url, json={"tipo": "entrada"}, headers=cabeceras_admin).json()["ocupados"] == 1
    respuesta = cliente.post(url, json={"tipo": "salida"}, headers=cabeceras_admin)
    assert respuesta.status_code == 201
    assert respuesta.json()["ocupados"] == 0


def test_admin_recibe_409_al_violar_la_capacidad(cliente, datos, cabeceras_admin):
    url = url_movimiento(datos["pequeno"])
    assert cliente.post(url, json={"tipo": "salida"}, headers=cabeceras_admin).status_code == 409
    for _ in range(3):
        cliente.post(url, json={"tipo": "entrada"}, headers=cabeceras_admin)
    respuesta = cliente.post(url, json={"tipo": "entrada"}, headers=cabeceras_admin)
    assert respuesta.status_code == 409
    assert "lleno" in respuesta.json()["detail"]


def test_admin_crea_parqueo_como_dato(cliente, datos, cabeceras_admin):
    nuevo = {
        "ciudad_id": datos["ciudad"].id,
        "nombre": "Nuevo",
        "latitud": -2.9,
        "longitud": -79.0,
        "capacidad": 25,
    }
    respuesta = cliente.post("/api/admin/parqueos", json=nuevo, headers=cabeceras_admin)
    assert respuesta.status_code == 201
    assert contiene(respuesta.json(), ocupados=0, disponibles=25)
    # Nombre repetido en la misma ciudad.
    assert cliente.post("/api/admin/parqueos", json=nuevo, headers=cabeceras_admin).status_code == 409


def test_admin_no_puede_crear_capacidad_invalida(cliente, datos, cabeceras_admin):
    invalido = {"ciudad_id": datos["ciudad"].id, "nombre": "X", "latitud": 0, "longitud": 0, "capacidad": 0}
    assert cliente.post("/api/admin/parqueos", json=invalido, headers=cabeceras_admin).status_code == 422


# --------------------------------------------------------------------------- dispositivos


def test_dispositivo_registra_en_su_propio_parqueo(cliente, datos, cabeceras_dispositivo):
    respuesta = cliente.post(
        "/api/dispositivos/movimientos", json={"tipo": "entrada"}, headers=cabeceras_dispositivo
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["id"] == datos["pequeno"].id
    assert respuesta.json()["ocupados"] == 1


@pytest.mark.parametrize("cabeceras", [{}, {"X-Clave-Dispositivo": "clave-falsa"}])
def test_dispositivo_sin_clave_valida_es_rechazado(cliente, datos, cabeceras):
    respuesta = cliente.post("/api/dispositivos/movimientos", json={"tipo": "entrada"}, headers=cabeceras)
    assert respuesta.status_code == 401


def test_token_de_admin_no_sirve_como_dispositivo(cliente, datos, cabeceras_admin):
    respuesta = cliente.post("/api/dispositivos/movimientos", json={"tipo": "entrada"}, headers=cabeceras_admin)
    assert respuesta.status_code == 401


def test_clave_de_dispositivo_no_da_acceso_de_admin(cliente, datos, cabeceras_dispositivo):
    respuesta = cliente.post(url_movimiento(datos["pequeno"]), json={"tipo": "entrada"}, headers=cabeceras_dispositivo)
    assert respuesta.status_code == 401


def test_dispositivo_inactivo_es_rechazado(cliente, datos, db, cabeceras_dispositivo):
    datos["sensor"].activo = False
    db.commit()
    respuesta = cliente.post("/api/dispositivos/movimientos", json={"tipo": "entrada"}, headers=cabeceras_dispositivo)
    assert respuesta.status_code == 401


def test_dispositivo_recibe_409_al_violar_la_capacidad(cliente, datos, cabeceras_dispositivo):
    url = "/api/dispositivos/movimientos"
    assert cliente.post(url, json={"tipo": "salida"}, headers=cabeceras_dispositivo).status_code == 409
    for _ in range(3):
        cliente.post(url, json={"tipo": "entrada"}, headers=cabeceras_dispositivo)
    assert cliente.post(url, json={"tipo": "entrada"}, headers=cabeceras_dispositivo).status_code == 409


def test_admin_crea_dispositivo_y_la_clave_funciona(cliente, datos, cabeceras_admin):
    grande = datos["grande"]
    creado = cliente.post(
        f"/api/admin/parqueos/{grande.id}/dispositivos", json={"nombre": "Barrera norte"}, headers=cabeceras_admin
    )
    assert creado.status_code == 201
    clave = creado.json()["clave"]
    respuesta = cliente.post(
        "/api/dispositivos/movimientos", json={"tipo": "entrada"}, headers={"X-Clave-Dispositivo": clave}
    )
    assert respuesta.json()["id"] == grande.id
