"""Cálculo de ocupación y validaciones de capacidad (capa de servicio)."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models import OrigenMovimiento, TipoMovimiento
from app.servicios import ocupacion
from app.servicios.errores import Conflicto

ENTRADA, SALIDA = TipoMovimiento.ENTRADA, TipoMovimiento.SALIDA
MANUAL, DISPOSITIVO = OrigenMovimiento.MANUAL, OrigenMovimiento.DISPOSITIVO


def registrar(db, parqueo, tipo, origen=MANUAL):
    return ocupacion.registrar_movimiento(db, parqueo.id, tipo, origen)[1]


# --------------------------------------------------------------------------- cálculo


def test_parqueo_sin_movimientos_tiene_ocupacion_cero(db, datos):
    assert ocupacion.calcular_ocupacion(db, datos["grande"].id) == 0


def test_ocupacion_es_entradas_menos_salidas(db, datos):
    grande = datos["grande"]
    for tipo in [ENTRADA, ENTRADA, ENTRADA, SALIDA, ENTRADA, SALIDA]:
        registrar(db, grande, tipo)
    assert ocupacion.calcular_ocupacion(db, grande.id) == 2


def test_registrar_devuelve_ocupacion_resultante(db, datos):
    assert registrar(db, datos["grande"], ENTRADA) == 1
    assert registrar(db, datos["grande"], ENTRADA, DISPOSITIVO) == 2
    assert registrar(db, datos["grande"], SALIDA) == 1


def test_manual_y_dispositivo_suman_en_el_mismo_conteo(db, datos):
    registrar(db, datos["grande"], ENTRADA, MANUAL)
    registrar(db, datos["grande"], ENTRADA, DISPOSITIVO)
    registrar(db, datos["grande"], SALIDA, DISPOSITIVO)
    assert ocupacion.calcular_ocupacion(db, datos["grande"].id) == 1


def test_listado_calcula_cada_parqueo_por_separado(db, datos):
    registrar(db, datos["pequeno"], ENTRADA)
    registrar(db, datos["grande"], ENTRADA)
    registrar(db, datos["grande"], ENTRADA)

    ocupados = {p.nombre: o for p, o in ocupacion.listar_parqueos(db)}
    assert ocupados == {"Pequeño": 1, "Grande": 2}


# --------------------------------------------------------------------------- capacidad


@pytest.mark.parametrize("origen", [MANUAL, DISPOSITIVO])
def test_no_se_supera_la_capacidad(db, datos, origen):
    pequeno = datos["pequeno"]  # capacidad 3
    for _ in range(3):
        registrar(db, pequeno, ENTRADA, origen)

    with pytest.raises(Conflicto, match="lleno"):
        registrar(db, pequeno, ENTRADA, origen)
    assert ocupacion.calcular_ocupacion(db, pequeno.id) == 3


@pytest.mark.parametrize("origen", [MANUAL, DISPOSITIVO])
def test_ocupacion_no_puede_ser_negativa(db, datos, origen):
    with pytest.raises(Conflicto, match="no tiene vehículos"):
        registrar(db, datos["pequeno"], SALIDA, origen)
    assert ocupacion.calcular_ocupacion(db, datos["pequeno"].id) == 0


def test_parqueo_inactivo_no_acepta_movimientos(db, datos):
    ocupacion.actualizar_parqueo(db, datos["pequeno"].id, {"activo": False})
    with pytest.raises(Conflicto, match="inactivo"):
        registrar(db, datos["pequeno"], ENTRADA)


def test_capacidad_no_puede_bajar_de_los_vehiculos_dentro(db, datos):
    grande = datos["grande"]
    for _ in range(4):
        registrar(db, grande, ENTRADA)

    with pytest.raises(Conflicto, match="4 vehículos"):
        ocupacion.actualizar_parqueo(db, grande.id, {"capacidad": 3})

    parqueo, ocupados = ocupacion.actualizar_parqueo(db, grande.id, {"capacidad": 4})
    assert (parqueo.capacidad, ocupados) == (4, 4)


def test_entradas_concurrentes_no_superan_la_capacidad(fabrica_sesiones, datos):
    """20 entradas simultáneas sobre un parqueo de capacidad 3: solo 3 deben aceptarse."""
    parqueo_id = datos["pequeno"].id

    def intentar_entrada(_):
        with fabrica_sesiones() as sesion:
            try:
                ocupacion.registrar_movimiento(sesion, parqueo_id, ENTRADA, DISPOSITIVO)
                return True
            except Conflicto:
                return False

    with ThreadPoolExecutor(max_workers=10) as ejecutor:
        resultados = list(ejecutor.map(intentar_entrada, range(20)))

    assert resultados.count(True) == 3
    with fabrica_sesiones() as sesion:
        assert ocupacion.calcular_ocupacion(sesion, parqueo_id) == 3
