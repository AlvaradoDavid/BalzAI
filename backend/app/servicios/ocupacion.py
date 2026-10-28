"""Cálculo de ocupación y registro de movimientos.

Regla central: ocupación = nº de entradas − nº de salidas de un parqueo.
Invariante: 0 <= ocupación <= capacidad, garantizada aquí para TODOS los orígenes
(panel de administración y dispositivos), incluso con peticiones concurrentes.
"""

from sqlalchemy import Select, case, func, insert, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import Ciudad, Movimiento, OrigenMovimiento, Parqueo, TipoMovimiento
from app.servicios.errores import Conflicto, NoEncontrado


# --------------------------------------------------------------------------- cálculo


def _consulta_ocupacion(parqueo_id: int | ColumnElement[int]) -> Select[tuple[int]]:
    """SELECT de la ocupación: suma +1 por entrada y −1 por salida."""
    delta = case((Movimiento.tipo == TipoMovimiento.ENTRADA, 1), else_=-1)
    return select(func.coalesce(func.sum(delta), 0)).where(Movimiento.parqueo_id == parqueo_id)


def ocupacion_de(parqueo_id: int | ColumnElement[int]):
    """Subconsulta escalar reutilizable. Con `Parqueo.id` queda correlacionada,
    lo que permite listar todos los parqueos con su ocupación en una sola consulta."""
    return _consulta_ocupacion(parqueo_id).scalar_subquery()


def calcular_ocupacion(db: Session, parqueo_id: int) -> int:
    return db.scalar(_consulta_ocupacion(parqueo_id))


# --------------------------------------------------------------------------- lectura


def listar_parqueos(
    db: Session, ciudad_slug: str | None = None, incluir_inactivos: bool = False
) -> list[tuple[Parqueo, int]]:
    consulta = select(Parqueo, ocupacion_de(Parqueo.id)).order_by(Parqueo.nombre)
    if ciudad_slug is not None:
        ciudad_id = db.scalar(select(Ciudad.id).where(Ciudad.slug == ciudad_slug))
        if ciudad_id is None:
            raise NoEncontrado(f"No existe la ciudad '{ciudad_slug}'.")
        consulta = consulta.where(Parqueo.ciudad_id == ciudad_id)
    if not incluir_inactivos:
        consulta = consulta.where(Parqueo.activo.is_(True))
    return [(parqueo, ocupados) for parqueo, ocupados in db.execute(consulta)]


def obtener_parqueo(db: Session, parqueo_id: int) -> tuple[Parqueo, int]:
    fila = db.execute(
        select(Parqueo, ocupacion_de(Parqueo.id)).where(Parqueo.id == parqueo_id)
    ).first()
    if fila is None:
        raise NoEncontrado(f"No existe el parqueo {parqueo_id}.")
    return fila[0], fila[1]


# --------------------------------------------------------------------------- escritura


def _bloquear_parqueo(db: Session, parqueo_id: int) -> Parqueo:
    """Bloquea la fila del parqueo hasta el commit (SELECT ... FOR UPDATE).

    En PostgreSQL esto serializa las operaciones concurrentes sobre un mismo parqueo.
    SQLite no admite FOR UPDATE (SQLAlchemy lo omite), pero allí cada sentencia de
    escritura toma el bloqueo de la base antes de leer; por eso las escrituras de
    abajo incluyen la validación dentro de la propia sentencia.
    """
    parqueo = db.scalar(select(Parqueo).where(Parqueo.id == parqueo_id).with_for_update())
    if parqueo is None:
        raise NoEncontrado(f"No existe el parqueo {parqueo_id}.")
    return parqueo


def registrar_movimiento(
    db: Session,
    parqueo_id: int,
    tipo: TipoMovimiento,
    origen: OrigenMovimiento,
    administrador_id: int | None = None,
    dispositivo_id: int | None = None,
) -> tuple[Parqueo, int]:
    """Registra una entrada o salida y devuelve el parqueo con su ocupación resultante.

    Lanza Conflicto si la entrada superaría la capacidad o si la salida dejaría la
    ocupación en negativo.
    """
    parqueo = _bloquear_parqueo(db, parqueo_id)
    if not parqueo.activo:
        raise Conflicto(f"El parqueo '{parqueo.nombre}' está inactivo.")

    # La regla de capacidad se evalúa en la MISMA sentencia que inserta:
    #   INSERT INTO movimientos (...) SELECT ... WHERE <ocupación cumple la regla>
    # Así no existe una ventana entre "comprobar" e "insertar" donde otra petición
    # concurrente pueda colarse y sobrepasar la capacidad.
    ocupados = ocupacion_de(parqueo_id)
    if tipo is TipoMovimiento.ENTRADA:
        capacidad = select(Parqueo.capacidad).where(Parqueo.id == parqueo_id).scalar_subquery()
        regla = ocupados < capacidad
    else:
        regla = ocupados > 0

    columnas = Movimiento.__table__.c
    valores = {
        "parqueo_id": parqueo_id,
        "tipo": tipo,
        "origen": origen,
        "administrador_id": administrador_id,
        "dispositivo_id": dispositivo_id,
    }
    fila = select(*(literal(valor, columnas[nombre].type) for nombre, valor in valores.items()))
    resultado = db.execute(
        insert(Movimiento.__table__).from_select(list(valores), fila.where(regla))
    )

    if resultado.rowcount != 1:
        db.rollback()
        if tipo is TipoMovimiento.ENTRADA:
            raise Conflicto(f"El parqueo '{parqueo.nombre}' está lleno.")
        raise Conflicto(f"El parqueo '{parqueo.nombre}' no tiene vehículos registrados para dar salida.")

    ocupacion = calcular_ocupacion(db, parqueo_id)  # leída aún dentro de la transacción
    db.commit()
    return parqueo, ocupacion


# --------------------------------------------------------------------------- gestión


def crear_parqueo(db: Session, datos: dict) -> tuple[Parqueo, int]:
    if db.get(Ciudad, datos["ciudad_id"]) is None:
        raise NoEncontrado(f"No existe la ciudad {datos['ciudad_id']}.")
    parqueo = Parqueo(**datos)
    db.add(parqueo)
    _confirmar(db, f"Ya existe un parqueo llamado '{datos['nombre']}' en esa ciudad.")
    return parqueo, 0


def actualizar_parqueo(db: Session, parqueo_id: int, cambios: dict) -> tuple[Parqueo, int]:
    parqueo = _bloquear_parqueo(db, parqueo_id)
    nueva_capacidad = cambios.pop("capacidad", None)

    if nueva_capacidad is not None:
        # Igual que en los movimientos: la capacidad no puede quedar por debajo de
        # los vehículos que ya están dentro, y se valida en la sentencia que escribe.
        resultado = db.execute(
            update(Parqueo.__table__)
            .where(Parqueo.id == parqueo_id, ocupacion_de(parqueo_id) <= nueva_capacidad)
            .values(capacidad=nueva_capacidad)
        )
        if resultado.rowcount != 1:
            ocupados = calcular_ocupacion(db, parqueo_id)
            db.rollback()
            raise Conflicto(
                f"La capacidad no puede ser menor que los {ocupados} vehículos que están dentro."
            )

    for campo, valor in cambios.items():
        setattr(parqueo, campo, valor)
    _confirmar(db, "Ya existe un parqueo con ese nombre en la ciudad.")
    db.refresh(parqueo)
    return parqueo, calcular_ocupacion(db, parqueo_id)


def _confirmar(db: Session, mensaje_duplicado: str) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise Conflicto(mensaje_duplicado) from error
