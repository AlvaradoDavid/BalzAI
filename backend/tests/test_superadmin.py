"""Pruebas del perfil Superadministrador, analíticas de flujo/tráfico y aislamiento de operadores."""

import pytest

from tests.conftest import CLAVE_SUPERADMIN


# --------------------------------------------------------------------------- control de acceso jerárquico


def test_login_superadmin_devuelve_rol_superadmin(cliente, datos):
    respuesta = cliente.post(
        "/api/auth/login", json={"usuario": "superadmin", "clave": CLAVE_SUPERADMIN}
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["rol"] == "superadmin"
    assert cuerpo["usuario"] == "superadmin"


@pytest.mark.parametrize(
    "metodo, ruta, cuerpo",
    [
        ("get", "/api/superadmin/analiticas", None),
        ("get", "/api/superadmin/operadores", None),
        ("get", "/api/superadmin/dispositivos", None),
        (
            "post",
            "/api/superadmin/ciudades",
            {"slug": "quito", "nombre": "Quito", "provincia": "Pichincha", "latitud": -0.18, "longitud": -78.46},
        ),
        (
            "post",
            "/api/superadmin/operadores",
            {"usuario": "nuevo_op", "clave": "clave123", "rol": "admin"},
        ),
    ],
)
def test_operador_normal_no_puede_acceder_a_rutas_superadmin(
    cliente, datos, cabeceras_admin, metodo, ruta, cuerpo
):
    peticion = getattr(cliente, metodo)
    kwargs = {"json": cuerpo} if cuerpo is not None else {}
    # Sin token -> 401
    assert peticion(ruta, **kwargs).status_code == 401
    # Con token de operador normal ('admin') -> 403 Forbidden
    assert peticion(ruta, headers=cabeceras_admin, **kwargs).status_code == 403


def test_superadmin_tambien_puede_operar_rutas_admin(cliente, datos, cabeceras_superadmin):
    pequeno = datos["pequeno"]
    respuesta = cliente.post(
        f"/api/admin/parqueos/{pequeno.id}/movimientos",
        json={"tipo": "entrada"},
        headers=cabeceras_superadmin,
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["ocupados"] == 1


# --------------------------------------------------------------------------- analíticas, flujo y tráfico


def test_analiticas_calcula_resumen_flujo_y_trafico(
    cliente, datos, cabeceras_admin, cabeceras_superadmin, cabeceras_dispositivo
):
    pequeno = datos["pequeno"]
    grande = datos["grande"]

    # 2 entradas manuales en Grande y 1 salida en Grande -> ocupados Grande = 1
    cliente.post(f"/api/admin/parqueos/{grande.id}/movimientos", json={"tipo": "entrada"}, headers=cabeceras_admin)
    cliente.post(f"/api/admin/parqueos/{grande.id}/movimientos", json={"tipo": "entrada"}, headers=cabeceras_admin)
    cliente.post(f"/api/admin/parqueos/{grande.id}/movimientos", json={"tipo": "salida"}, headers=cabeceras_admin)
    # 1 entrada por sensor en Pequeño -> ocupados Pequeño = 1
    cliente.post("/api/dispositivos/movimientos", json={"tipo": "entrada"}, headers=cabeceras_dispositivo)

    respuesta = cliente.get(
        "/api/superadmin/analiticas", params={"horas": 12}, headers=cabeceras_superadmin
    )
    assert respuesta.status_code == 200
    analiticas = respuesta.json()

    resumen = analiticas["resumen"]
    assert resumen["ciudades_total"] == 1
    assert resumen["parqueos_activos"] == 2
    assert resumen["capacidad_total"] == 13
    assert resumen["ocupados_actuales"] == 2
    assert resumen["disponibles_actuales"] == 11
    assert resumen["movimientos_totales"] == 4
    assert resumen["entradas_totales"] == 3
    assert resumen["salidas_totales"] == 1
    assert resumen["por_origen"] == {"manual": 3, "dispositivo": 1}

    # Flujo horario: la suma en la ventana de 12 h debe coincidir con los 4 movimientos
    assert len(analiticas["flujo_horario"]) == 12
    assert sum(p["entradas"] for p in analiticas["flujo_horario"]) == 3
    assert sum(p["salidas"] for p in analiticas["flujo_horario"]) == 1

    # Tráfico por parqueadero
    por_nombre = {t["nombre"]: t for t in analiticas["trafico_por_parqueo"]}
    assert por_nombre["Grande"]["entradas_totales"] == 2
    assert por_nombre["Grande"]["salidas_totales"] == 1
    assert por_nombre["Grande"]["ocupados"] == 1
    assert por_nombre["Pequeño"]["dispositivos_activos"] == 1

    # Bitácora de movimientos recientes
    assert len(analiticas["movimientos_recientes"]) == 4
    assert analiticas["movimientos_recientes"][0]["parqueo_id"] == pequeno.id
    assert analiticas["movimientos_recientes"][0]["origen"] == "dispositivo"


# --------------------------------------------------------------------------- ciudades, operadores y alcance


def test_superadmin_crea_ciudad_y_aparece_en_mapa_publico(cliente, datos, cabeceras_superadmin):
    nueva = {
        "slug": "loja",
        "nombre": "Loja",
        "provincia": "Loja",
        "latitud": -3.9931,
        "longitud": -79.2042,
        "zoom": 14,
    }
    creada = cliente.post("/api/superadmin/ciudades", json=nueva, headers=cabeceras_superadmin)
    assert creada.status_code == 201
    # Slug duplicado -> 409
    assert cliente.post("/api/superadmin/ciudades", json=nueva, headers=cabeceras_superadmin).status_code == 409

    ciudades_publicas = [c["slug"] for c in cliente.get("/api/ciudades").json()]
    assert "loja" in ciudades_publicas


def test_operador_asignado_a_un_parqueadero_solo_puede_operar_el_suyo(
    cliente, datos, cabeceras_superadmin
):
    pequeno = datos["pequeno"]
    grande = datos["grande"]

    # El Superadmin crea un operador asignado únicamente al parqueadero "Pequeño"
    creado = cliente.post(
        "/api/superadmin/operadores",
        json={
            "usuario": "guardia_pequeno",
            "nombre": "Guardia Pequeño",
            "clave": "clave-guardia-123",
            "rol": "admin",
            "parqueo_id": pequeno.id,
        },
        headers=cabeceras_superadmin,
    )
    assert creado.status_code == 201
    assert creado.json()["parqueo_id"] == pequeno.id

    # Inicia sesión el operador restringido
    login = cliente.post(
        "/api/auth/login", json={"usuario": "guardia_pequeno", "clave": "clave-guardia-123"}
    )
    assert login.status_code == 200
    cabeceras_guardia = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # En su listado solo ve su parqueadero asignado ("Pequeño")
    listado = cliente.get("/api/admin/parqueos", headers=cabeceras_guardia).json()
    assert [p["id"] for p in listado] == [pequeno.id]

    # Puede registrar movimiento en "Pequeño"
    ok = cliente.post(
        f"/api/admin/parqueos/{pequeno.id}/movimientos",
        json={"tipo": "entrada"},
        headers=cabeceras_guardia,
    )
    assert ok.status_code == 201

    # No puede registrar movimiento ni editar en "Grande" -> 403 Forbidden
    prohibido = cliente.post(
        f"/api/admin/parqueos/{grande.id}/movimientos",
        json={"tipo": "entrada"},
        headers=cabeceras_guardia,
    )
    assert prohibido.status_code == 403

    # Tampoco puede dar de alta un nuevo parqueadero -> 403 Forbidden
    crear_otro = cliente.post(
        "/api/admin/parqueos",
        json={"ciudad_id": datos["ciudad"].id, "nombre": "Intruso", "latitud": 0, "longitud": 0, "capacidad": 10},
        headers=cabeceras_guardia,
    )
    assert crear_otro.status_code == 403


def test_superadmin_no_puede_desactivarse_a_si_mismo(cliente, datos, cabeceras_superadmin):
    yo = datos["superadmin"].id
    respuesta = cliente.patch(
        f"/api/superadmin/operadores/{yo}",
        json={"activo": False},
        headers=cabeceras_superadmin,
    )
    assert respuesta.status_code == 409
