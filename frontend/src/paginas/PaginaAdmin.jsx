import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { admin, cerrarSesion, iniciarSesion, obtenerCiudades, sesionGuardada } from "../api.js";
import BarraOcupacion from "../componentes/BarraOcupacion.jsx";
import FormularioParqueo from "../componentes/FormularioParqueo.jsx";
import { vibrar } from "../fisica.js";

/**
 * Panel operativo para dueños de parqueaderos y personal de seguridad encargado:
 *  - registrar entradas y salidas manualmente (o acompañar a sensores automáticos);
 *  - gestionar los datos de su(s) parqueadero(s).
 */
export default function PaginaAdmin() {
  const [sesion, setSesion] = useState(sesionGuardada);
  const [avisoSesion, setAvisoSesion] = useState(null);

  const salir = useCallback((aviso = null) => {
    cerrarSesion();
    setSesion(null);
    setAvisoSesion(aviso);
  }, []);

  if (!sesion?.token) {
    return <FormularioLogin aviso={avisoSesion} onIngresar={setSesion} />;
  }
  return <PanelOperador sesion={sesion} onSalir={salir} />;
}

// --------------------------------------------------------------------------- login

function FormularioLogin({ aviso, onIngresar }) {
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      onIngresar(await iniciarSesion(usuario, clave));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <div className="pagina-centrada">
      <form className="tarjeta login" onSubmit={enviar}>
        <span className="insignia-rol">Operación de Parqueadero</span>
        <h1>Acceso de Operadores</h1>
        <p className="secundario">
          Para dueños de parqueaderos y personal de seguridad encargado de registrar entradas,
          salidas y disponibilidad.
        </p>
        {aviso && <p className="aviso">{aviso}</p>}
        <label>
          Usuario
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
        <button type="submit" className="boton primario" disabled={enviando}>
          {enviando ? "Ingresando…" : "Ingresar al panel"}
        </button>
      </form>
    </div>
  );
}

// --------------------------------------------------------------------------- panel

function PanelOperador({ sesion, onSalir }) {
  const { token, rol, usuario, nombre, parqueo_id: parqueoAsignadoId } = sesion;
  const puedeCrearParqueo = rol === "superadmin" || parqueoAsignadoId == null;

  const [ciudades, setCiudades] = useState([]);
  const [parqueos, setParqueos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [mensaje, setMensaje] = useState(null); // { tipo: "ok" | "error", texto }
  const [editandoId, setEditandoId] = useState(null);
  const [creando, setCreando] = useState(false);
  const [ocupadoId, setOcupadoId] = useState(null);

  /** Ejecuta una llamada protegida; si el token venció, vuelve al login. */
  const protegido = useCallback(
    async (llamada) => {
      try {
        return await llamada();
      } catch (err) {
        if (err.estado === 401) {
          onSalir("Tu sesión expiró. Vuelve a ingresar.");
        }
        throw err;
      }
    },
    [onSalir],
  );

  const recargar = useCallback(
    () =>
      protegido(() => admin.listarParqueos(token))
        .then(setParqueos)
        .catch((err) => setMensaje({ tipo: "error", texto: err.message }))
        .finally(() => setCargando(false)),
    [protegido, token],
  );

  useEffect(() => {
    recargar();
    obtenerCiudades().then(setCiudades).catch(() => {});
  }, [recargar]);

  const reemplazar = (actualizado) =>
    setParqueos((lista) => lista.map((p) => (p.id === actualizado.id ? actualizado : p)));

  const registrar = async (parqueo, tipo) => {
    setOcupadoId(parqueo.id);
    try {
      const actualizado = await protegido(() => admin.registrarMovimiento(token, parqueo.id, tipo));
      vibrar(10);
      reemplazar(actualizado);
      setMensaje({
        tipo: "ok",
        texto: `${tipo === "entrada" ? "Entrada" : "Salida"} registrada en ${parqueo.nombre}: ${actualizado.disponibles} disponibles.`,
      });
    } catch (err) {
      vibrar([16, 40, 16]);
      setMensaje({ tipo: "error", texto: err.message });
      if (err.estado === 409) recargar();
    } finally {
      setOcupadoId(null);
    }
  };

  const guardarEdicion = async (id, cambios) => {
    const actualizado = await protegido(() => admin.actualizarParqueo(token, id, cambios));
    reemplazar(actualizado);
    setEditandoId(null);
    setMensaje({ tipo: "ok", texto: `Parqueo "${actualizado.nombre}" actualizado.` });
  };

  const guardarNuevo = async (datos) => {
    const creado = await protegido(() => admin.crearParqueo(token, datos));
    setParqueos((lista) => [...lista, creado].sort((a, b) => a.nombre.localeCompare(b.nombre)));
    setCreando(false);
    setMensaje({ tipo: "ok", texto: `Parqueo "${creado.nombre}" creado.` });
  };

  const nombreCiudad = (id) => ciudades.find((c) => c.id === id)?.nombre ?? "";

  return (
    <div className="pagina-admin">
      <div className="encabezado-admin">
        <div>
          <span className="insignia-rol">
            {rol === "superadmin"
              ? "Superadministrador"
              : parqueoAsignadoId
                ? "Operador de Parqueadero Asignado"
                : "Operador de Parqueaderos"}
          </span>
          <h1>Operación de Parqueaderos</h1>
          <p className="secundario sin-margen">
            Sesión activa: <strong>{nombre || usuario}</strong> ({usuario})
          </p>
        </div>
        <div className="acciones">
          {rol === "superadmin" && (
            <Link to="/superadmin" className="boton">
              Ir a Control de la App →
            </Link>
          )}
          <button type="button" className="boton" onClick={recargar}>
            Actualizar
          </button>
          {puedeCrearParqueo && (
            <button
              type="button"
              className="boton primario"
              onClick={() => setCreando(true)}
              disabled={creando}
            >
              + Nuevo parqueo
            </button>
          )}
          <button type="button" className="boton" onClick={() => onSalir()}>
            Cerrar sesión
          </button>
        </div>
      </div>

      {mensaje && (
        <p className={mensaje.tipo === "ok" ? "exito" : "error"} role="status">
          {mensaje.texto}
        </p>
      )}

      {creando && (
        <section className="tarjeta">
          <h2>Nuevo parqueo</h2>
          <FormularioParqueo
            ciudades={ciudades}
            onGuardar={guardarNuevo}
            onCancelar={() => setCreando(false)}
          />
        </section>
      )}

      {cargando ? (
        <p>Cargando…</p>
      ) : (
        <ul className="lista-admin">
          {parqueos.map((p) => (
            <li key={p.id} className={`tarjeta fila-parqueo${p.activo ? "" : " inactivo"}`}>
              <div className="fila-datos">
                <div className="fila-nombre">
                  <strong>{p.nombre}</strong>
                  <span className="secundario">
                    {nombreCiudad(p.ciudad_id)}
                    {p.direccion ? ` · ${p.direccion}` : ""}
                    {p.activo ? "" : " · INACTIVO"}
                  </span>
                </div>
                <div className="fila-ocupacion">
                  <span>
                    <strong>{p.ocupados}</strong> / {p.capacidad} ocupados ·{" "}
                    <strong>{p.disponibles}</strong> libres
                  </span>
                  <BarraOcupacion parqueo={p} />
                </div>
                <div className="acciones">
                  <button
                    type="button"
                    className="boton entrada"
                    onClick={() => registrar(p, "entrada")}
                    disabled={!p.activo || p.disponibles <= 0 || ocupadoId === p.id}
                    title="Registrar la entrada de un vehículo"
                  >
                    + Entrada
                  </button>
                  <button
                    type="button"
                    className="boton salida"
                    onClick={() => registrar(p, "salida")}
                    disabled={!p.activo || p.ocupados <= 0 || ocupadoId === p.id}
                    title="Registrar la salida de un vehículo"
                  >
                    − Salida
                  </button>
                  <button
                    type="button"
                    className="boton"
                    onClick={() => setEditandoId(editandoId === p.id ? null : p.id)}
                  >
                    Editar
                  </button>
                </div>
              </div>
              {editandoId === p.id && (
                <FormularioParqueo
                  inicial={p}
                  onGuardar={(cambios) => guardarEdicion(p.id, cambios)}
                  onCancelar={() => setEditandoId(null)}
                />
              )}
            </li>
          ))}
          {parqueos.length === 0 && (
            <li className="secundario">No hay parqueos asignados o registrados.</li>
          )}
        </ul>
      )}
    </div>
  );
}
