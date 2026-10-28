import { useState } from "react";

const VACIO = { ciudad_id: "", nombre: "", direccion: "", latitud: "", longitud: "", capacidad: "" };

/**
 * Formulario para crear o editar un parqueo.
 * - Crear: recibe `ciudades` y envía todos los campos.
 * - Editar: recibe `inicial` y envía solo los campos modificados.
 */
export default function FormularioParqueo({ inicial, ciudades = [], onGuardar, onCancelar }) {
  const editando = Boolean(inicial);
  const [valores, setValores] = useState(() =>
    editando
      ? { ...inicial, direccion: inicial.direccion ?? "" }
      : { ...VACIO, ciudad_id: ciudades[0]?.id ?? "" },
  );
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  const cambiar = (campo) => (e) =>
    setValores((v) => ({ ...v, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const enviar = async (e) => {
    e.preventDefault();
    const datos = {
      nombre: valores.nombre.trim(),
      direccion: valores.direccion.trim() || null,
      latitud: Number(valores.latitud),
      longitud: Number(valores.longitud),
      capacidad: Number(valores.capacidad),
    };
    if (editando) {
      datos.activo = valores.activo;
    } else {
      datos.ciudad_id = Number(valores.ciudad_id);
    }
    const cuerpo = editando
      ? Object.fromEntries(Object.entries(datos).filter(([campo, valor]) => valor !== (inicial[campo] ?? null)))
      : datos;

    if (editando && Object.keys(cuerpo).length === 0) return onCancelar();

    setGuardando(true);
    setError(null);
    try {
      await onGuardar(cuerpo);
    } catch (err) {
      setError(err.message);
      setGuardando(false);
    }
  };

  return (
    <form className="formulario" onSubmit={enviar}>
      {!editando && (
        <label>
          Ciudad
          <select value={valores.ciudad_id} onChange={cambiar("ciudad_id")} required>
            {ciudades.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Nombre
        <input value={valores.nombre} onChange={cambiar("nombre")} maxLength={150} required />
      </label>
      <label className="ancho">
        Dirección
        <input value={valores.direccion} onChange={cambiar("direccion")} maxLength={255} />
      </label>
      <label>
        Latitud
        <input type="number" step="any" min={-90} max={90} value={valores.latitud} onChange={cambiar("latitud")} required />
      </label>
      <label>
        Longitud
        <input type="number" step="any" min={-180} max={180} value={valores.longitud} onChange={cambiar("longitud")} required />
      </label>
      <label>
        Capacidad
        <input type="number" min={1} step={1} value={valores.capacidad} onChange={cambiar("capacidad")} required />
      </label>
      {editando && (
        <label className="casilla">
          <input type="checkbox" checked={valores.activo} onChange={cambiar("activo")} />
          Activo (visible en el mapa)
        </label>
      )}
      {error && <p className="error ancho">{error}</p>}
      <div className="acciones ancho">
        <button type="submit" className="boton primario" disabled={guardando}>
          {guardando ? "Guardando…" : editando ? "Guardar cambios" : "Crear parqueo"}
        </button>
        <button type="button" className="boton" onClick={onCancelar} disabled={guardando}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
