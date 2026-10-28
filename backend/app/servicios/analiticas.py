"""Analíticas de plataforma, flujo y tráfico vehicular, y control global para Superadmin."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.esquemas import (
    AnaliticasSalida,
    DesgloseOrigen,
    DispositivoSalida,
    HoraPico,
    MovimientoRecienteSalida,
    OperadorSalida,
    PuntoFlujoHorario,
    ResumenAnaliticas,
    TraficoParqueo,
)
from app.models import (
    Administrador,
    Ciudad,
    Dispositivo,
    Movimiento,
    OrigenMovimiento,
    Parqueo,
    RolAdministrador,
    TipoMovimiento,
)
from app.seguridad import hashear_clave
from app.servicios.errores import Conflicto, NoEncontrado


def _asegurar_utc(fecha: datetime) -> datetime:
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def obtener_analiticas(
    db: Session, ciudad_slug: str | None = None, ventana_horas: int = 24
) -> AnaliticasSalida:
    """Construye el panel analítico global de ocupación, flujo horario y tráfico."""
    ventana_horas = max(1, min(ventana_horas, 168))  # entre 1 h y 7 días
    ahora = datetime.now(timezone.utc)
    inicio_ventana = (ahora - timedelta(hours=ventana_horas - 1)).replace(
        minute=0, second=0, microsecond=0
    )

    ciudades = {c.id: c for c in db.scalars(select(Ciudad)).all()}
    ciudad_id_filtro: int | None = None
    if ciudad_slug:
        ciudad_encontrada = next((c for c in ciudades.values() if c.slug == ciudad_slug), None)
        if ciudad_encontrada is None:
            raise NoEncontrado(f"No existe la ciudad '{ciudad_slug}'.")
        ciudad_id_filtro = ciudad_encontrada.id

    consulta_parqueos = select(Parqueo).order_by(Parqueo.nombre)
    if ciudad_id_filtro is not None:
        consulta_parqueos = consulta_parqueos.where(Parqueo.ciudad_id == ciudad_id_filtro)
    parqueos = list(db.scalars(consulta_parqueos).all())
    ids_parqueos = [p.id for p in parqueos]

    # Conteos históricos de entradas, salidas y orígenes por parqueo en una sola consulta.
    totales_por_parqueo: dict[int, dict[str, int]] = {
        pid: {"entradas": 0, "salidas": 0, "manual": 0, "dispositivo": 0} for pid in ids_parqueos
    }
    if ids_parqueos:
        filas_totales = db.execute(
            select(
                Movimiento.parqueo_id,
                func.coalesce(
                    func.sum(case((Movimiento.tipo == TipoMovimiento.ENTRADA, 1), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(case((Movimiento.tipo == TipoMovimiento.SALIDA, 1), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(case((Movimiento.origen == OrigenMovimiento.MANUAL, 1), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(
                        case((Movimiento.origen == OrigenMovimiento.DISPOSITIVO, 1), else_=0)
                    ),
                    0,
                ),
            )
            .where(Movimiento.parqueo_id.in_(ids_parqueos))
            .group_by(Movimiento.parqueo_id)
        ).all()
        for pid, ent, sal, man, disp in filas_totales:
            totales_por_parqueo[pid] = {
                "entradas": int(ent),
                "salidas": int(sal),
                "manual": int(man),
                "dispositivo": int(disp),
            }

    # Dispositivos activos y operadores asignados por parqueadero.
    sensores_por_parqueo: dict[int, int] = dict(
        db.execute(
            select(Dispositivo.parqueo_id, func.count(Dispositivo.id))
            .where(Dispositivo.activo.is_(True))
            .group_by(Dispositivo.parqueo_id)
        ).all()
    )
    operadores_por_parqueo: dict[int, int] = dict(
        db.execute(
            select(Administrador.parqueo_id, func.count(Administrador.id))
            .where(
                Administrador.activo.is_(True),
                Administrador.parqueo_id.is_not(None),
            )
            .group_by(Administrador.parqueo_id)
        ).all()
    )

    # Flujo horario dentro de la ventana solicitada.
    numero_cubetas = min(ventana_horas, 24)
    paso_horas = max(1, ventana_horas // numero_cubetas)
    cubetas: list[dict] = []
    for i in range(numero_cubetas):
        desde = inicio_ventana + timedelta(hours=i * paso_horas)
        hasta = desde + timedelta(hours=paso_horas)
        cubetas.append(
            {
                "desde": desde,
                "hasta": hasta,
                "hora_iso": desde.isoformat(),
                "etiqueta": desde.strftime("%H:%M") if ventana_horas <= 24 else desde.strftime("%d/%m %Hh"),
                "entradas": 0,
                "salidas": 0,
            }
        )

    movimientos_ventana_por_parqueo: dict[int, int] = {pid: 0 for pid in ids_parqueos}
    entradas_ventana = 0
    salidas_ventana = 0

    if ids_parqueos:
        filas_ventana = db.execute(
            select(Movimiento.parqueo_id, Movimiento.tipo, Movimiento.creado_en).where(
                Movimiento.parqueo_id.in_(ids_parqueos),
                Movimiento.creado_en >= inicio_ventana.replace(tzinfo=None),
            )
        ).all()
        for pid, tipo, creado_en in filas_ventana:
            instante = _asegurar_utc(creado_en)
            if instante < inicio_ventana:
                continue
            movimientos_ventana_por_parqueo[pid] = movimientos_ventana_por_parqueo.get(pid, 0) + 1
            if tipo is TipoMovimiento.ENTRADA:
                entradas_ventana += 1
            else:
                salidas_ventana += 1

            indice = int((instante - inicio_ventana).total_seconds() // (3600 * paso_horas))
            if 0 <= indice < len(cubetas):
                if tipo is TipoMovimiento.ENTRADA:
                    cubetas[indice]["entradas"] += 1
                else:
                    cubetas[indice]["salidas"] += 1

    flujo_horario = [
        PuntoFlujoHorario(
            hora_iso=c["hora_iso"],
            etiqueta=c["etiqueta"],
            entradas=c["entradas"],
            salidas=c["salidas"],
            flujo_neto=c["entradas"] - c["salidas"],
            total=c["entradas"] + c["salidas"],
        )
        for c in cubetas
    ]

    mejor_cubeta = max(flujo_horario, key=lambda p: p.total, default=None)
    hora_pico = (
        HoraPico(hora=mejor_cubeta.etiqueta, movimientos=mejor_cubeta.total)
        if mejor_cubeta and mejor_cubeta.total > 0
        else HoraPico(hora=None, movimientos=0)
    )

    # Tráfico detallado por parqueadero.
    trafico_por_parqueo: list[TraficoParqueo] = []
    capacidad_total = 0
    ocupados_actuales = 0
    parqueos_activos = 0
    parqueos_inactivos = 0
    entradas_totales = 0
    salidas_totales = 0
    origen_manual = 0
    origen_dispositivo = 0

    for p in parqueos:
        t = totales_por_parqueo[p.id]
        ocupados = max(0, t["entradas"] - t["salidas"])
        disponibles = max(0, p.capacidad - ocupados)
        porcentaje = round((ocupados / p.capacidad) * 100, 1) if p.capacidad > 0 else 0.0
        rotacion = round(t["entradas"] / p.capacidad, 2) if p.capacidad > 0 else 0.0

        if p.activo:
            parqueos_activos += 1
            capacidad_total += p.capacidad
            ocupados_actuales += ocupados
        else:
            parqueos_inactivos += 1

        entradas_totales += t["entradas"]
        salidas_totales += t["salidas"]
        origen_manual += t["manual"]
        origen_dispositivo += t["dispositivo"]

        trafico_por_parqueo.append(
            TraficoParqueo(
                id=p.id,
                nombre=p.nombre,
                ciudad_id=p.ciudad_id,
                ciudad_nombre=ciudades[p.ciudad_id].nombre if p.ciudad_id in ciudades else "",
                activo=p.activo,
                capacidad=p.capacidad,
                ocupados=ocupados,
                disponibles=disponibles,
                porcentaje_ocupacion=porcentaje,
                entradas_totales=t["entradas"],
                salidas_totales=t["salidas"],
                movimientos_ventana=movimientos_ventana_por_parqueo.get(p.id, 0),
                indice_rotacion=rotacion,
                dispositivos_activos=sensores_por_parqueo.get(p.id, 0),
                operadores_asignados=operadores_por_parqueo.get(p.id, 0),
            )
        )

    # Bitácora de los últimos 25 movimientos.
    movimientos_recientes: list[MovimientoRecienteSalida] = []
    if ids_parqueos:
        mapa_parqueos = {p.id: p.nombre for p in parqueos}
        mapa_admins = dict(db.execute(select(Administrador.id, Administrador.usuario)).all())
        mapa_sensores = dict(db.execute(select(Dispositivo.id, Dispositivo.nombre)).all())

        ultimos = db.scalars(
            select(Movimiento)
            .where(Movimiento.parqueo_id.in_(ids_parqueos))
            .order_by(Movimiento.id.desc())
            .limit(25)
        ).all()
        for m in ultimos:
            if m.origen is OrigenMovimiento.MANUAL:
                actor = mapa_admins.get(m.administrador_id, "operador")
            else:
                actor = mapa_sensores.get(m.dispositivo_id, "sensor")
            movimientos_recientes.append(
                MovimientoRecienteSalida(
                    id=m.id,
                    parqueo_id=m.parqueo_id,
                    parqueo_nombre=mapa_parqueos.get(m.parqueo_id, ""),
                    tipo=m.tipo,
                    origen=m.origen,
                    actor=actor,
                    creado_en=_asegurar_utc(m.creado_en),
                )
            )

    operadores_activos = int(
        db.scalar(
            select(func.count(Administrador.id)).where(
                Administrador.activo.is_(True),
                Administrador.rol == RolAdministrador.ADMIN,
            )
        )
        or 0
    )
    dispositivos_activos = sum(sensores_por_parqueo.get(pid, 0) for pid in ids_parqueos)
    disponibles_actuales = max(0, capacidad_total - ocupados_actuales)
    porcentaje_global = (
        round((ocupados_actuales / capacidad_total) * 100, 1) if capacidad_total > 0 else 0.0
    )

    resumen = ResumenAnaliticas(
        ciudades_total=len(ciudades),
        parqueos_activos=parqueos_activos,
        parqueos_inactivos=parqueos_inactivos,
        capacidad_total=capacidad_total,
        ocupados_actuales=ocupados_actuales,
        disponibles_actuales=disponibles_actuales,
        porcentaje_ocupacion=porcentaje_global,
        movimientos_totales=entradas_totales + salidas_totales,
        entradas_totales=entradas_totales,
        salidas_totales=salidas_totales,
        movimientos_ventana=entradas_ventana + salidas_ventana,
        entradas_ventana=entradas_ventana,
        salidas_ventana=salidas_ventana,
        por_origen=DesgloseOrigen(manual=origen_manual, dispositivo=origen_dispositivo),
        hora_pico=hora_pico,
        operadores_activos=operadores_activos,
        dispositivos_activos=dispositivos_activos,
    )

    return AnaliticasSalida(
        ventana_horas=ventana_horas,
        ciudad_filtro=ciudad_slug,
        resumen=resumen,
        flujo_horario=flujo_horario,
        trafico_por_parqueo=trafico_por_parqueo,
        movimientos_recientes=movimientos_recientes,
    )


# --------------------------------------------------------------------------- ciudades


def crear_ciudad(db: Session, datos: dict) -> Ciudad:
    ciudad = Ciudad(**datos)
    db.add(ciudad)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise Conflicto(f"Ya existe una ciudad con el slug '{datos['slug']}'.") from error
    db.refresh(ciudad)
    return ciudad


def actualizar_ciudad(db: Session, ciudad_id: int, cambios: dict) -> Ciudad:
    ciudad = db.get(Ciudad, ciudad_id)
    if ciudad is None:
        raise NoEncontrado(f"No existe la ciudad {ciudad_id}.")
    for campo, valor in cambios.items():
        if valor is not None:
            setattr(ciudad, campo, valor)
    db.commit()
    db.refresh(ciudad)
    return ciudad


# --------------------------------------------------------------------------- operadores


def listar_operadores(db: Session) -> list[OperadorSalida]:
    parqueos = dict(db.execute(select(Parqueo.id, Parqueo.nombre)).all())
    conteos = dict(
        db.execute(
            select(Movimiento.administrador_id, func.count(Movimiento.id))
            .where(Movimiento.administrador_id.is_not(None))
            .group_by(Movimiento.administrador_id)
        ).all()
    )
    cuentas = db.scalars(select(Administrador).order_by(Administrador.rol.desc(), Administrador.usuario)).all()
    return [
        OperadorSalida(
            id=a.id,
            usuario=a.usuario,
            nombre=a.nombre,
            rol=a.rol,
            parqueo_id=a.parqueo_id,
            parqueo_nombre=parqueos.get(a.parqueo_id) if a.parqueo_id else None,
            activo=a.activo,
            movimientos_registrados=int(conteos.get(a.id, 0)),
            creado_en=_asegurar_utc(a.creado_en),
        )
        for a in cuentas
    ]


def crear_operador(db: Session, datos: dict) -> OperadorSalida:
    parqueo_id = datos.get("parqueo_id")
    if parqueo_id is not None and db.get(Parqueo, parqueo_id) is None:
        raise NoEncontrado(f"No existe el parqueo {parqueo_id}.")

    nuevo = Administrador(
        usuario=datos["usuario"],
        nombre=datos.get("nombre"),
        clave_hash=hashear_clave(datos["clave"]),
        rol=datos.get("rol", RolAdministrador.ADMIN),
        parqueo_id=parqueo_id if datos.get("rol") != RolAdministrador.SUPERADMIN else None,
        activo=True,
    )
    db.add(nuevo)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise Conflicto(f"Ya existe el usuario '{datos['usuario']}'.") from error
    db.refresh(nuevo)

    parqueo_nombre = db.scalar(select(Parqueo.nombre).where(Parqueo.id == nuevo.parqueo_id)) if nuevo.parqueo_id else None
    return OperadorSalida(
        id=nuevo.id,
        usuario=nuevo.usuario,
        nombre=nuevo.nombre,
        rol=nuevo.rol,
        parqueo_id=nuevo.parqueo_id,
        parqueo_nombre=parqueo_nombre,
        activo=nuevo.activo,
        movimientos_registrados=0,
        creado_en=_asegurar_utc(nuevo.creado_en),
    )


def actualizar_operador(
    db: Session, operador_id: int, cambios: dict, superadmin_actual_id: int
) -> OperadorSalida:
    operador = db.get(Administrador, operador_id)
    if operador is None:
        raise NoEncontrado(f"No existe la cuenta {operador_id}.")

    if operador.id == superadmin_actual_id:
        if cambios.get("activo") is False:
            raise Conflicto("No puedes desactivar tu propia cuenta de Superadministrador.")
        if cambios.get("rol") is not None and cambios["rol"] != RolAdministrador.SUPERADMIN:
            raise Conflicto("No puedes quitarte el rol de Superadministrador a ti mismo.")

    if "parqueo_id" in cambios and cambios["parqueo_id"] is not None:
        if db.get(Parqueo, cambios["parqueo_id"]) is None:
            raise NoEncontrado(f"No existe el parqueo {cambios['parqueo_id']}.")

    if "clave" in cambios and cambios["clave"]:
        operador.clave_hash = hashear_clave(cambios.pop("clave"))
    else:
        cambios.pop("clave", None)

    for campo, valor in cambios.items():
        setattr(operador, campo, valor)

    if operador.rol is RolAdministrador.SUPERADMIN:
        operador.parqueo_id = None

    db.commit()
    db.refresh(operador)
    parqueo_nombre = (
        db.scalar(select(Parqueo.nombre).where(Parqueo.id == operador.parqueo_id))
        if operador.parqueo_id
        else None
    )
    movimientos = int(
        db.scalar(
            select(func.count(Movimiento.id)).where(Movimiento.administrador_id == operador.id)
        )
        or 0
    )
    return OperadorSalida(
        id=operador.id,
        usuario=operador.usuario,
        nombre=operador.nombre,
        rol=operador.rol,
        parqueo_id=operador.parqueo_id,
        parqueo_nombre=parqueo_nombre,
        activo=operador.activo,
        movimientos_registrados=movimientos,
        creado_en=_asegurar_utc(operador.creado_en),
    )


# --------------------------------------------------------------------------- dispositivos


def listar_dispositivos(db: Session) -> list[DispositivoSalida]:
    parqueos = dict(db.execute(select(Parqueo.id, Parqueo.nombre)).all())
    conteos = dict(
        db.execute(
            select(Movimiento.dispositivo_id, func.count(Movimiento.id))
            .where(Movimiento.dispositivo_id.is_not(None))
            .group_by(Movimiento.dispositivo_id)
        ).all()
    )
    sensores = db.scalars(select(Dispositivo).order_by(Dispositivo.parqueo_id, Dispositivo.nombre)).all()
    return [
        DispositivoSalida(
            id=d.id,
            nombre=d.nombre,
            parqueo_id=d.parqueo_id,
            parqueo_nombre=parqueos.get(d.parqueo_id, ""),
            activo=d.activo,
            movimientos_registrados=int(conteos.get(d.id, 0)),
            creado_en=_asegurar_utc(d.creado_en),
        )
        for d in sensores
    ]


def actualizar_dispositivo(db: Session, dispositivo_id: int, cambios: dict) -> DispositivoSalida:
    sensor = db.get(Dispositivo, dispositivo_id)
    if sensor is None:
        raise NoEncontrado(f"No existe el dispositivo {dispositivo_id}.")
    for campo, valor in cambios.items():
        if valor is not None:
            setattr(sensor, campo, valor)
    db.commit()
    db.refresh(sensor)
    parqueo_nombre = db.scalar(select(Parqueo.nombre).where(Parqueo.id == sensor.parqueo_id)) or ""
    movimientos = int(
        db.scalar(select(func.count(Movimiento.id)).where(Movimiento.dispositivo_id == sensor.id))
        or 0
    )
    return DispositivoSalida(
        id=sensor.id,
        nombre=sensor.nombre,
        parqueo_id=sensor.parqueo_id,
        parqueo_nombre=parqueo_nombre,
        activo=sensor.activo,
        movimientos_registrados=movimientos,
        creado_en=_asegurar_utc(sensor.creado_en),
    )
