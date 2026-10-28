import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  admin,
  cerrarSesion,
  iniciarSesion,
  obtenerCiudades,
  sesionGuardada,
  superadmin,
} from "../api.js";
import BarraOcupacion from "../componentes/BarraOcupacion.jsx";
import { vibrar } from "../fisica.js";

/**
 * Consola ejecutiva del Administrador de la Aplicación (Superadministrador):
 *  - Analíticas de plataforma, flujo horario (entradas vs. salidas), rotación y bitácora en vivo.
 *  - Gestión de dueños de parqueaderos / personal de seguridad (operadores).
 *  - Control de ciudades y sensores/dispositivos IoT.
 */
export default function PaginaSuperAdmin() {
  const [sesion, setSesion] = useState(sesionGuardada);
  const [aviso, setAviso] = useState(null);

  const salir = useCallback((mensaje = null) => {
    cerrarSesion();
    setSesion(null);
    setAviso(mensaje);
  }, []);

  if (!sesion?.token || sesion.rol !== "superadmin") {
    return (
      <LoginSuperAdmin
        sesionActual={sesion}
        aviso={aviso}
        onIngresar={setSesion}
        onCerrarActual={() => salir()}
      />
    );
  }

  return <ConsolaSuperAdmin sesion={sesion} onSalir={salir} />;
}

// --------------------------------------------------------------------------- login superadmin

function LoginSuperAdmin({ sesionActual, aviso, onIngresar, onCerrarActual }) {
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const nuevaSesion = await iniciarSesion(usuario, clave);
      if (nuevaSesion.rol !== "superadmin") {
        setError(
          "Esta cuenta corresponde a un Operador de Parqueadero. Para usar esta consola ingresa con una cuenta de Superadministrador.",
        );
        setEnviando(false);
        return;
      }
      vibrar(10);
      onIngresar(nuevaSesion);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <div className="pagina-centrada">
      <form className="tarjeta login" onSubmit={enviar}>
        <span className="insignia-rol super">Superadministración de la App</span>
        <h1>Control de la Aplicación</h1>
        <p className="secundario">
          Perfil superior para controlar toda la plataforma, monitorear flujo y tráfico vehicular,
          y gestionar ciudades, operadores y sensores.
        </p>
        {sesionActual?.token && sesionActual.rol !== "superadmin" && (
          <div className="aviso">
            Estás conectado como operador (<strong>{sesionActual.usuario}</strong>). Puedes{" "}
            <Link to="/admin">ir a Operación de Parqueo</Link> o ingresar abajo como
            Superadministrador.
          </div>
        )}
        {aviso && <p className="aviso">{aviso}</p>}
        <label>
          Usuario Superadmin
          <input
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="username"
            required
            autoFocus
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="acciones">
          <button type="submit" className="boton primario" disabled={enviando}>
            {enviando ? "Verificando…" : "Abrir consola"}
          </button>
          {sesionActual?.token && (
            <button type="button" className="boton" onClick={onCerrarActual}>
              Cerrar sesión actual
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

// --------------------------------------------------------------------------- consola principal

function ConsolaSuperAdmin({ sesion, onSalir }) {
  const { token, usuario, nombre } = sesion;
  const [pestana, setPestana] = useState("analiticas"); // "analiticas" | "operadores" | "plataforma"
  const [ciudadFiltro, setCiudadFiltro] = useState("");
  const [horasVentana, setHorasVentana] = useState(24);

  const [ciudades, setCiudades] = useState([]);
  const [parqueos, setParqueos] = useState([]);
  const [analiticas, setAnaliticas] = useState(null);
  const [operadores, setOperadores] = useState([]);
  const [dispositivos, setDispositivos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [mensaje, setMensaje] = useState(null);

  const protegido = useCallback(
    async (llamada) => {
      try {
        return await llamada();
      } catch (err) {
        if (err.estado === 401 || err.estado === 403) {
          onSalir("Tu sesión de Superadministrador expiró.");
        }
        throw err;
      }
    },
    [onSalir],
  );

  const cargarTodo = useCallback(async () => {
    setCargando(true);
    try {
      const [datosAnaliticas, listaCiudades, listaParqueos, listaOperadores, listaDispositivos] =
        await Promise.all([
          protegido(() =>
            superadmin.obtenerAnaliticas(token, { ciudad: ciudadFiltro, horas: horasVentana }),
          ),
          obtenerCiudades(),
          protegido(() => admin.listarParqueos(token)),
          protegido(() => superadmin.listarOperadores(token)),
          protegido(() => superadmin.listarDispositivos(token)),
        ]);
      setAnaliticas(datosAnaliticas);
      setCiudades(listaCiudades);
      setParqueos(listaParqueos);
      setOperadores(listaOperadores);
      setDispositivos(listaDispositivos);
    } catch (err) {
      setMensaje({ tipo: "error", texto: err.message });
    } finally {
      setCargando(false);
    }
  }, [protegido, token, ciudadFiltro, horasVentana]);

  useEffect(() => {
    cargarTodo();
  }, [cargarTodo]);

  const cambiarPestana = (nueva) => {
    vibrar(6);
    setMensaje(null);
    setPestana(nueva);
  };

  return (
    <div className="pagina-admin pagina-superadmin">
      <div className="encabezado-admin">
        <div>
          <span className="insignia-rol super">Superadministrador de la Aplicación</span>
          <h1>Centro de Control y Analíticas</h1>
          <p className="secundario sin-margen">
            Sesión: <strong>{nombre || usuario}</strong> · Control global de tráfico, parqueaderos,
            ciudades y operadores
          </p>
        </div>
        <div className="acciones">
          <Link to="/admin" className="boton">
            Vista Operador
          </Link>
          <button type="button" className="boton" onClick={cargarTodo}>
            Refrescar datos
          </button>
          <button type="button" className="boton" onClick={() => onSalir()}>
            Cerrar sesión
          </button>
        </div>
      </div>

      {/* Control segmentado al estilo Apple */}
      <div className="segmentos" role="tablist" aria-label="Secciones de Superadministración">
        <button
          type="button"
          role="tab"
          aria-selected={pestana === "analiticas"}
          className={`segmento${pestana === "analiticas" ? " activo" : ""}`}
          onClick={() => cambiarPestana("analiticas")}
        >
          Analíticas, Flujo y Tráfico
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={pestana === "operadores"}
          className={`segmento${pestana === "operadores" ? " activo" : ""}`}
          onClick={() => cambiarPestana("operadores")}
        >
          Dueños y Operadores ({operadores.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={pestana === "plataforma"}
          className={`segmento${pestana === "plataforma" ? " activo" : ""}`}
          onClick={() => cambiarPestana("plataforma")}
        >
          Ciudades y Sensores IoT ({dispositivos.length})
        </button>
      </div>

      {mensaje && (
        <p className={mensaje.tipo === "ok" ? "exito" : "error"} role="status">
          {mensaje.texto}
        </p>
      )}

      {cargando && !analiticas ? (
        <p>Cargando métricas de la plataforma…</p>
      ) : (
        <>
          {pestana === "analiticas" && analiticas && (
            <VistaAnaliticas
              analiticas={analiticas}
              ciudades={ciudades}
              ciudadFiltro={ciudadFiltro}
              horasVentana={horasVentana}
              onCambiarCiudad={setCiudadFiltro}
              onCambiarHoras={setHorasVentana}
            />
          )}
          {pestana === "operadores" && (
            <VistaOperadores
              token={token}
              protegido={protegido}
              operadores={operadores}
              parqueos={parqueos}
              miUsuario={usuario}
              onActualizarLista={setOperadores}
              onMensaje={setMensaje}
            />
          )}
          {pestana === "plataforma" && (
            <VistaPlataforma
              token={token}
              protegido={protegido}
              ciudades={ciudades}
              parqueos={parqueos}
              dispositivos={dispositivos}
              onRecargar={cargarTodo}
              onMensaje={setMensaje}
            />
          )}
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- 1. Analíticas y Tráfico

function VistaAnaliticas({
  analiticas,
  ciudades,
  ciudadFiltro,
  horasVentana,
  onCambiarCiudad,
  onCambiarHoras,
}) {
  const { resumen, flujo_horario, trafico_por_parqueo, movimientos_recientes } = analiticas;
  const maxMovimientosHora = Math.max(1, ...flujo_horario.map((p) => Math.max(p.entradas, p.salidas)));
  const porcentajeSensores =
    resumen.movimientos_totales > 0
      ? Math.round((resumen.por_origen.dispositivo / resumen.movimientos_totales) * 100)
      : 0;

  return (
    <div className="seccion-super">
      <div className="tarjeta filtros-analiticas">
        <label className="filtro-en-linea">
          Ciudad
          <select value={ciudadFiltro} onChange={(e) => onCambiarCiudad(e.target.value)}>
            <option value="">Todas las ciudades ({ciudades.length})</option>
            {ciudades.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nombre} ({c.provincia})
              </option>
            ))}
          </select>
        </label>
        <label className="filtro-en-linea">
          Ventana de tráfico
          <select
            value={horasVentana}
            onChange={(e) => onCambiarHoras(Number(e.target.value))}
          >
            <option value={6}>Últimas 6 horas</option>
            <option value={12}>Últimas 12 horas</option>
            <option value={24}>Últimas 24 horas</option>
            <option value={72}>Últimos 3 días (72 h)</option>
            <option value={168}>Últimos 7 días</option>
          </select>
        </label>
      </div>

      {/* KPIs principales */}
      <div className="rejilla-kpis">
        <article className="tarjeta kpi">
          <span className="kpi-titulo">Ocupación Global Actual</span>
          <strong className="kpi-valor">{resumen.porcentaje_ocupacion}%</strong>
          <span className="kpi-sub">
            <b>{resumen.ocupados_actuales}</b> ocupados · <b>{resumen.disponibles_actuales}</b>{" "}
            libres de {resumen.capacidad_total}
          </span>
        </article>

        <article className="tarjeta kpi">
          <span className="kpi-titulo">Flujo en Ventana ({horasVentana} h)</span>
          <strong className="kpi-valor">{resumen.movimientos_ventana}</strong>
          <span className="kpi-sub">
            <b className="texto-libre">+{resumen.entradas_ventana} entradas</b> ·{" "}
            <b className="texto-lleno">−{resumen.salidas_ventana} salidas</b>
          </span>
        </article>

        <article className="tarjeta kpi">
          <span className="kpi-titulo">Tráfico Histórico Acumulado</span>
          <strong className="kpi-valor">{resumen.movimientos_totales}</strong>
          <span className="kpi-sub">
            {resumen.entradas_totales} entradas · {resumen.salidas_totales} salidas
          </span>
        </article>

        <article className="tarjeta kpi">
          <span className="kpi-titulo">Hora Pico de Demanda</span>
          <strong className="kpi-valor">{resumen.hora_pico.hora ?? "—"}</strong>
          <span className="kpi-sub">
            {resumen.hora_pico.movimientos} vehículos movilizados en esa franja
          </span>
        </article>

        <article className="tarjeta kpi">
          <span className="kpi-titulo">Origen de Datos (Sensores vs. Manual)</span>
          <strong className="kpi-valor">{porcentajeSensores}% IoT</strong>
          <span className="kpi-sub">
            {resumen.por_origen.dispositivo} por sensor · {resumen.por_origen.manual} manuales
          </span>
        </article>

        <article className="tarjeta kpi">
          <span className="kpi-titulo">Cobertura Operativa</span>
          <strong className="kpi-valor">{resumen.parqueos_activos} parqueos</strong>
          <span className="kpi-sub">
            {resumen.ciudades_total} ciudades · {resumen.operadores_activos} operadores ·{" "}
            {resumen.dispositivos_activos} sensores
          </span>
        </article>
      </div>

      {/* Gráfico de flujo y tráfico por franja horaria */}
      <section className="tarjeta">
        <div className="encabezado-seccion">
          <div>
            <h2>Flujo y Tráfico Vehicular por Hora</h2>
            <p className="secundario sin-margen">
              Comparativa de entradas y salidas registradas en cada franja dentro de las últimas{" "}
              {horasVentana} horas.
            </p>
          </div>
          <div className="leyenda-flujo">
            <span>
              <i className="punto nivel-libre" /> Entradas
            </span>
            <span>
              <i className="punto nivel-lleno" /> Salidas
            </span>
          </div>
        </div>

        <div className="grafico-flujo" role="img" aria-label="Gráfico de barras de entradas y salidas por hora">
          {flujo_horario.map((punto) => {
            const altEntrada = Math.round((punto.entradas / maxMovimientosHora) * 100);
            const altSalida = Math.round((punto.salidas / maxMovimientosHora) * 100);
            return (
              <div
                key={punto.hora_iso}
                className="columna-flujo"
                title={`${punto.etiqueta}: +${punto.entradas} entradas, −${punto.salidas} salidas (neto ${punto.flujo_neto >= 0 ? "+" : ""}${punto.flujo_neto})`}
              >
                <div className="barras-par">
                  <div
                    className="barra-vertical nivel-libre"
                    style={{ height: `${Math.max(punto.entradas > 0 ? 8 : 2, altEntrada)}%` }}
                  />
                  <div
                    className="barra-vertical nivel-lleno"
                    style={{ height: `${Math.max(punto.salidas > 0 ? 8 : 2, altSalida)}%` }}
                  />
                </div>
                <span className="cifra-columna">{punto.total > 0 ? punto.total : "·"}</span>
                <span className="etiqueta-columna">{punto.etiqueta}</span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Tabla de rendimiento y rotación por parqueadero */}
      <section className="tarjeta">
        <h2>Saturación, Flujo y Rotación por Parqueadero</h2>
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Parqueadero</th>
                <th>Ocupación actual</th>
                <th>Entradas</th>
                <th>Salidas</th>
                <th>Tráfico ({horasVentana} h)</th>
                <th>Rotación</th>
                <th>Sensores / Operadores</th>
              </tr>
            </thead>
            <tbody>
              {trafico_por_parqueo.map((t) => (
                <tr key={t.id} className={t.activo ? "" : "fila-inactiva"}>
                  <td>
                    <strong>{t.nombre}</strong>
                    <div className="secundario">
                      {t.ciudad_nombre}
                      {t.activo ? "" : " · INACTIVO"}
                    </div>
                  </td>
                  <td className="celda-ocupacion">
                    <div className="fila-entre">
                      <span>
                        <b>{t.ocupados}</b> / {t.capacidad} ({t.porcentaje_ocupacion}%)
                      </span>
                      <span className="secundario">{t.disponibles} libres</span>
                    </div>
                    <BarraOcupacion parqueo={t} />
                  </td>
                  <td className="texto-libre">+{t.entradas_totales}</td>
                  <td className="texto-lleno">−{t.salidas_totales}</td>
                  <td>
                    <b>{t.movimientos_ventana}</b> mov.
                  </td>
                  <td>{t.indice_rotacion}x</td>
                  <td>
                    {t.dispositivos_activos} sensores · {t.operadores_asignados} op.
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Bitácora de tráfico en tiempo real */}
      <section className="tarjeta">
        <h2>Bitácora de Tráfico en Vivo (Últimos 25 movimientos)</h2>
        {movimientos_recientes.length === 0 ? (
          <p className="secundario">Aún no se registran movimientos.</p>
        ) : (
          <div className="tabla-contenedor">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fecha / Hora</th>
                  <th>Parqueadero</th>
                  <th>Movimiento</th>
                  <th>Canal</th>
                  <th>Registrado por</th>
                </tr>
              </thead>
              <tbody>
                {movimientos_recientes.map((m) => (
                  <tr key={m.id}>
                    <td className="secundario">
                      {new Date(m.creado_en).toLocaleString("es-EC", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        day: "2-digit",
                        month: "2-digit",
                      })}
                    </td>
                    <td>
                      <strong>{m.parqueo_nombre}</strong>
                    </td>
                    <td>
                      <span
                        className={`insignia-tabla ${
                          m.tipo === "entrada" ? "nivel-libre" : "nivel-lleno"
                        }`}
                      >
                        {m.tipo === "entrada" ? "+ Entrada" : "− Salida"}
                      </span>
                    </td>
                    <td>
                      <span className="insignia-canal">
                        {m.origen === "dispositivo" ? "Sensor IoT" : "Panel Manual"}
                      </span>
                    </td>
                    <td>{m.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- 2. Operadores y Dueños

function VistaOperadores({
  token,
  protegido,
  operadores,
  parqueos,
  miUsuario,
  onActualizarLista,
  onMensaje,
}) {
  const [usuario, setUsuario] = useState("");
  const [nombre, setNombre] = useState("");
  const [clave, setClave] = useState("");
  const [rol, setRol] = useState("admin");
  const [parqueoId, setParqueoId] = useState("");
  const [guardando, setGuardando] = useState(false);

  const crear = async (e) => {
    e.preventDefault();
    setGuardando(true);
    try {
      const creado = await protegido(() =>
        superadmin.crearOperador(token, {
          usuario: usuario.trim(),
          nombre: nombre.trim() || null,
          clave,
          rol,
          parqueo_id: rol === "admin" && parqueoId ? Number(parqueoId) : null,
        }),
      );
      vibrar(10);
      onActualizarLista((lista) => [...lista, creado]);
      setUsuario("");
      setNombre("");
      setClave("");
      setParqueoId("");
      onMensaje({
        tipo: "ok",
        texto: `Cuenta "${creado.usuario}" (${creado.rol}) creada correctamente.`,
      });
    } catch (err) {
      onMensaje({ tipo: "error", texto: err.message });
    } finally {
      setGuardando(false);
    }
  };

  const cambiarEstado = async (op) => {
    try {
      const actualizado = await protegido(() =>
        superadmin.actualizarOperador(token, op.id, { activo: !op.activo }),
      );
      onActualizarLista((lista) => lista.map((x) => (x.id === op.id ? actualizado : x)));
      onMensaje({
        tipo: "ok",
        texto: `Cuenta "${actualizado.usuario}" ${actualizado.activo ? "reactivada" : "desactivada"}.`,
      });
    } catch (err) {
      onMensaje({ tipo: "error", texto: err.message });
    }
  };

  const cambiarAsignacion = async (op, nuevoParqueoId) => {
    try {
      const actualizado = await protegido(() =>
        superadmin.actualizarOperador(token, op.id, {
          parqueo_id: nuevoParqueoId ? Number(nuevoParqueoId) : null,
        }),
      );
      onActualizarLista((lista) => lista.map((x) => (x.id === op.id ? actualizado : x)));
      onMensaje({
        tipo: "ok",
        texto: `Asignación de "${actualizado.usuario}" actualizada.`,
      });
    } catch (err) {
      onMensaje({ tipo: "error", texto: err.message });
    }
  };

  return (
    <div className="seccion-super">
      <section className="tarjeta">
        <h2>Registrar Dueño de Parqueadero, Guardia de Seguridad o Superadmin</h2>
        <p className="secundario">
          Asigna un parqueadero específico para que el operador solo pueda administrar y registrar
          entradas/salidas de ese punto, o déjalo en «Todos los parqueaderos» para operadores
          generales.
        </p>
        <form className="formulario" onSubmit={crear}>
          <label>
            Usuario
            <input
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              placeholder="ej. dueno_sanblas"
              maxLength={60}
              required
            />
          </label>
          <label>
            Nombre o cargo
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="ej. Guardia Turno Mañana"
              maxLength={120}
            />
          </label>
          <label>
            Contraseña inicial
            <input
              type="password"
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              minLength={6}
              placeholder="Mínimo 6 caracteres"
              required
            />
          </label>
          <label>
            Perfil de acceso
            <select value={rol} onChange={(e) => setRol(e.target.value)}>
              <option value="admin">Operador / Dueño de Parqueadero</option>
              <option value="superadmin">Superadministrador de la App</option>
            </select>
          </label>
          {rol === "admin" && (
            <label>
              Parqueadero asignado
              <select value={parqueoId} onChange={(e) => setParqueoId(e.target.value)}>
                <option value="">Todos los parqueaderos</option>
                {parqueos.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="acciones ancho">
            <button type="submit" className="boton primario" disabled={guardando}>
              {guardando ? "Creando cuenta…" : "+ Crear cuenta"}
            </button>
          </div>
        </form>
      </section>

      <section className="tarjeta">
        <h2>Cuentas Registradas</h2>
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Usuario / Nombre</th>
                <th>Rol</th>
                <th>Parqueadero Asignado</th>
                <th>Movimientos</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {operadores.map((op) => (
                <tr key={op.id} className={op.activo ? "" : "fila-inactiva"}>
                  <td>
                    <strong>{op.usuario}</strong>
                    {op.nombre && <div className="secundario">{op.nombre}</div>}
                  </td>
                  <td>
                    <span className={`insignia-rol${op.rol === "superadmin" ? " super" : ""}`}>
                      {op.rol === "superadmin" ? "Superadmin App" : "Operador Parqueo"}
                    </span>
                  </td>
                  <td>
                    {op.rol === "superadmin" ? (
                      <span className="secundario">Acceso global a toda la app</span>
                    ) : (
                      <select
                        value={op.parqueo_id ?? ""}
                        onChange={(e) => cambiarAsignacion(op, e.target.value)}
                        aria-label={`Parqueadero asignado a ${op.usuario}`}
                      >
                        <option value="">Todos los parqueaderos</option>
                        {parqueos.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.nombre}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td>{op.movimientos_registrados}</td>
                  <td>{op.activo ? "Activo" : "Inactivo"}</td>
                  <td>
                    {op.usuario !== miUsuario && (
                      <button
                        type="button"
                        className="boton"
                        onClick={() => cambiarEstado(op)}
                      >
                        {op.activo ? "Desactivar" : "Activar"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- 3. Ciudades y Sensores IoT

function VistaPlataforma({
  token,
  protegido,
  ciudades,
  parqueos,
  dispositivos,
  onRecargar,
  onMensaje,
}) {
  const [slug, setSlug] = useState("");
  const [nombreCiudad, setNombreCiudad] = useState("");
  const [provincia, setProvincia] = useState("");
  const [latitud, setLatitud] = useState("");
  const [longitud, setLongitud] = useState("");
  const [zoom, setZoom] = useState(14);
  const [creandoCiudad, setCreandoCiudad] = useState(false);

  const [parqueoSensorId, setParqueoSensorId] = useState(parqueos[0]?.id ?? "");
  const [nombreSensor, setNombreSensor] = useState("");
  const [claveRecienCreada, setClaveRecienCreada] = useState(null);
  const [creandoSensor, setCreandoSensor] = useState(false);

  const guardarCiudad = async (e) => {
    e.preventDefault();
    setCreandoCiudad(true);
    try {
      const creada = await protegido(() =>
        superadmin.crearCiudad(token, {
          slug: slug.trim().toLowerCase(),
          nombre: nombreCiudad.trim(),
          provincia: provincia.trim(),
          latitud: Number(latitud),
          longitud: Number(longitud),
          zoom: Number(zoom),
        }),
      );
      vibrar(10);
      setSlug("");
      setNombreCiudad("");
      setProvincia("");
      setLatitud("");
      setLongitud("");
      onMensaje({
        tipo: "ok",
        texto: `Ciudad "${creada.nombre}" agregada a la plataforma.`,
      });
      onRecargar();
    } catch (err) {
      onMensaje({ tipo: "error", texto: err.message });
    } finally {
      setCreandoCiudad(false);
    }
  };

  const guardarSensor = async (e) => {
    e.preventDefault();
    if (!parqueoSensorId) return;
    setCreandoSensor(true);
    try {
      const creado = await protegido(() =>
        admin.crearDispositivo(token, Number(parqueoSensorId), nombreSensor.trim()),
      );
      vibrar(10);
      setClaveRecienCreada(creado);
      setNombreSensor("");
      onRecargar();
    } catch (err) {
      onMensaje({ tipo: "error", texto: err.message });
    } finally {
      setCreandoSensor(false);
    }
  };

  const alternarDispositivo = async (d) => {
    try {
      await protegido(() =>
        superadmin.actualizarDispositivo(token, d.id, { activo: !d.activo }),
      );
      onMensaje({
        tipo: "ok",
        texto: `Dispositivo "${d.nombre}" ${!d.activo ? "activado" : "desactivado"}.`,
      });
      onRecargar();
    } catch (err) {
      onMensaje({ tipo: "error", texto: err.message });
    }
  };

  return (
    <div className="seccion-super">
      <section className="tarjeta">
        <h2>Ciudades de la Plataforma ({ciudades.length})</h2>
        <p className="secundario">
          Escalar a cualquier ciudad del Ecuador es agregar un registro: el selector del mapa
          público se habilita automáticamente cuando hay más de una ciudad.
        </p>
        <div className="chips-ciudades">
          {ciudades.map((c) => (
            <span key={c.id} className="chip-ciudad">
              <strong>{c.nombre}</strong> ({c.provincia}) · <code>{c.slug}</code> · [{c.latitud},{" "}
              {c.longitud}]
            </span>
          ))}
        </div>

        <form className="formulario" onSubmit={guardarCiudad}>
          <label>
            Slug (URL)
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="ej. quito"
              pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
              required
            />
          </label>
          <label>
            Nombre de la ciudad
            <input
              value={nombreCiudad}
              onChange={(e) => setNombreCiudad(e.target.value)}
              placeholder="ej. Quito"
              required
            />
          </label>
          <label>
            Provincia
            <input
              value={provincia}
              onChange={(e) => setProvincia(e.target.value)}
              placeholder="ej. Pichincha"
              required
            />
          </label>
          <label>
            Latitud
            <input
              type="number"
              step="any"
              min={-90}
              max={90}
              value={latitud}
              onChange={(e) => setLatitud(e.target.value)}
              placeholder="-0.1807"
              required
            />
          </label>
          <label>
            Longitud
            <input
              type="number"
              step="any"
              min={-180}
              max={180}
              value={longitud}
              onChange={(e) => setLongitud(e.target.value)}
              placeholder="-78.4678"
              required
            />
          </label>
          <label>
            Zoom inicial
            <input
              type="number"
              min={5}
              max={20}
              value={zoom}
              onChange={(e) => setZoom(e.target.value)}
              required
            />
          </label>
          <div className="acciones ancho">
            <button type="submit" className="boton primario" disabled={creandoCiudad}>
              {creandoCiudad ? "Agregando…" : "+ Agregar ciudad"}
            </button>
          </div>
        </form>
      </section>

      <section className="tarjeta">
        <h2>Sensores y Barreras Automáticas IoT</h2>
        <p className="secundario">
          Cada dispositivo tiene una clave única (cabecera <code>X-Clave-Dispositivo</code>) que
          solo permite reportar entradas y salidas de su parqueadero asignado.
        </p>

        {claveRecienCreada && (
          <div className="exito">
            <strong>Clave generada para «{claveRecienCreada.nombre}»</strong> (guárdala ahora, no
            se vuelve a mostrar):{" "}
            <code className="codigo-clave">{claveRecienCreada.clave}</code>
          </div>
        )}

        <form className="formulario" onSubmit={guardarSensor}>
          <label>
            Parqueadero
            <select
              value={parqueoSensorId}
              onChange={(e) => setParqueoSensorId(e.target.value)}
              required
            >
              {parqueos.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </select>
          </label>
          <label className="ancho-2">
            Nombre del sensor o barrera
            <input
              value={nombreSensor}
              onChange={(e) => setNombreSensor(e.target.value)}
              placeholder="ej. Espira Magnética Acceso Norte"
              maxLength={120}
              required
            />
          </label>
          <div className="acciones ancho">
            <button type="submit" className="boton primario" disabled={creandoSensor}>
              {creandoSensor ? "Generando clave…" : "+ Generar clave de sensor"}
            </button>
          </div>
        </form>

        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Dispositivo</th>
                <th>Parqueadero</th>
                <th>Lecturas enviadas</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {dispositivos.map((d) => (
                <tr key={d.id} className={d.activo ? "" : "fila-inactiva"}>
                  <td>
                    <strong>{d.nombre}</strong>
                  </td>
                  <td>{d.parqueo_nombre}</td>
                  <td>{d.movimientos_registrados}</td>
                  <td>{d.activo ? "En línea" : "Revocado"}</td>
                  <td>
                    <button
                      type="button"
                      className="boton"
                      onClick={() => alternarDispositivo(d)}
                    >
                      {d.activo ? "Revocar" : "Reactivar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
