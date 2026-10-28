import { useCallback, useEffect, useState } from "react";
import { obtenerCiudades, obtenerParqueo, obtenerParqueos } from "../api.js";
import MapaParqueos from "../componentes/MapaParqueos.jsx";
import PanelParqueo from "../componentes/PanelParqueo.jsx";
import { vibrar } from "../fisica.js";

const CIUDAD_INICIAL = import.meta.env.VITE_CIUDAD_INICIAL ?? "cuenca";
const SEGUNDOS_REFRESCO = 15; // la ocupación cambia con cada entrada/salida

/** Vista pública (solo lectura): mapa de parqueos y tarjeta flotante del parqueo seleccionado. */
export default function PaginaMapa() {
  const [ciudades, setCiudades] = useState([]);
  const [ciudadSlug, setCiudadSlug] = useState(null);
  const [parqueos, setParqueos] = useState([]);
  const [seleccionadoId, setSeleccionadoId] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [errorDetalle, setErrorDetalle] = useState(null);
  const [error, setError] = useState(null);

  // 1. Ciudades: vienen de la base, por lo que agregar una ciudad no requiere tocar el frontend.
  useEffect(() => {
    obtenerCiudades()
      .then((lista) => {
        setCiudades(lista);
        const inicial = lista.find((c) => c.slug === CIUDAD_INICIAL) ?? lista[0];
        setCiudadSlug(inicial?.slug ?? null);
        if (!inicial) setError("Aún no hay ciudades registradas.");
      })
      .catch((e) => setError(e.message));
  }, []);

  // 2. Parqueos de la ciudad elegida, refrescados periódicamente.
  useEffect(() => {
    if (!ciudadSlug) return undefined;
    let vigente = true;
    const cargar = () =>
      obtenerParqueos(ciudadSlug)
        .then((lista) => {
          if (!vigente) return;
          setParqueos(lista);
          setError(null);
        })
        .catch((e) => vigente && setError(e.message));

    cargar();
    const intervalo = setInterval(cargar, SEGUNDOS_REFRESCO * 1000);
    return () => {
      vigente = false;
      clearInterval(intervalo);
    };
  }, [ciudadSlug]);

  // Mantiene el panel sincronizado con cada refresco del listado.
  useEffect(() => {
    if (seleccionadoId == null) return;
    const actualizado = parqueos.find((p) => p.id === seleccionadoId);
    if (actualizado) setDetalle(actualizado);
  }, [parqueos, seleccionadoId]);

  // 3. Respuesta inmediata (0 ms): pintamos al instante el dato en memoria y en paralelo
  // consultamos /api/parqueos/{id} para confirmar la cifra más reciente.
  const seleccionar = useCallback(
    (id) => {
      vibrar(8);
      setSeleccionadoId(id);
      setErrorDetalle(null);
      const enMemoria = parqueos.find((p) => p.id === id);
      if (enMemoria) setDetalle(enMemoria);
      obtenerParqueo(id)
        .then(setDetalle)
        .catch((e) => setErrorDetalle(e.message));
    },
    [parqueos],
  );

  const cerrarPanel = useCallback(() => {
    setSeleccionadoId(null);
    setDetalle(null);
    setErrorDetalle(null);
  }, []);

  const cambiarCiudad = (slug) => {
    cerrarPanel();
    setParqueos([]);
    setCiudadSlug(slug);
  };

  const ciudad = ciudades.find((c) => c.slug === ciudadSlug);
  const totalDisponibles = parqueos.reduce((suma, p) => suma + p.disponibles, 0);

  return (
    <div className="pagina-mapa">
      <div className="barra-mapa cristal" role="region" aria-label="Resumen de la ciudad">
        {ciudades.length > 1 ? (
          <select
            value={ciudadSlug ?? ""}
            onChange={(e) => cambiarCiudad(e.target.value)}
            aria-label="Ciudad"
          >
            {ciudades.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nombre}
              </option>
            ))}
          </select>
        ) : (
          ciudad && <strong>{ciudad.nombre}</strong>
        )}
        {ciudad && (
          <span className="resumen">
            {parqueos.length} parqueos · <b>{totalDisponibles}</b> espacios libres
          </span>
        )}
        {error && <span className="error">{error}</span>}
      </div>

      <div className="mapa-lienzo">
        {ciudad ? (
          <MapaParqueos
            ciudad={ciudad}
            parqueos={parqueos}
            seleccionadoId={seleccionadoId}
            onSeleccionar={seleccionar}
          />
        ) : (
          <div className="mapa mapa-cargando">{error ? "Sin datos" : "Cargando mapa…"}</div>
        )}
        <PanelParqueo
          parqueo={seleccionadoId != null ? detalle : null}
          error={errorDetalle}
          onCerrar={cerrarPanel}
        />
      </div>
    </div>
  );
}
