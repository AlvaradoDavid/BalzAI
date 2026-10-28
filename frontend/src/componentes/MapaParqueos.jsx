/**
 * Mapa con Leaflet + OpenStreetMap: librería libre y ligera, y teselas gratuitas que no
 * requieren clave de API, suficiente para el MVP y sin costos por uso al escalar a más ciudades.
 */
import { useEffect, useMemo } from "react";
import { MapContainer, Marker, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import { nivelOcupacion } from "../ocupacion.js";

/** Marcador HTML con el número de espacios libres (evita los íconos PNG de Leaflet). */
function iconoParqueo(parqueo, seleccionado) {
  const nivel = nivelOcupacion(parqueo);
  return L.divIcon({
    className: "",
    html: `<div class="marcador nivel-${nivel}${seleccionado ? " seleccionado" : ""}">
             <span>${parqueo.disponibles}</span>
           </div>`,
    iconSize: [40, 40],
    iconAnchor: [20, 40],
    tooltipAnchor: [0, -40],
  });
}

/** Recentra el mapa cuando cambia la ciudad (MapContainer solo usa `center` al montarse). */
function CentrarEnCiudad({ ciudad }) {
  const mapa = useMap();
  useEffect(() => {
    mapa.setView([ciudad.latitud, ciudad.longitud], ciudad.zoom);
  }, [mapa, ciudad]);
  return null;
}

export default function MapaParqueos({ ciudad, parqueos, seleccionadoId, onSeleccionar }) {
  const marcadores = useMemo(
    () =>
      parqueos.map((p) => (
        <Marker
          key={p.id}
          position={[p.latitud, p.longitud]}
          icon={iconoParqueo(p, p.id === seleccionadoId)}
          zIndexOffset={p.id === seleccionadoId ? 1000 : 0}
          eventHandlers={{ click: () => onSeleccionar(p.id) }}
          title={p.nombre}
          alt={`${p.nombre}: ${p.disponibles} espacios disponibles`}
          keyboard
        >
          <Tooltip direction="top">{p.nombre}</Tooltip>
        </Marker>
      )),
    [parqueos, seleccionadoId, onSeleccionar],
  );

  return (
    <MapContainer
      className="mapa"
      center={[ciudad.latitud, ciudad.longitud]}
      zoom={ciudad.zoom}
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <CentrarEnCiudad ciudad={ciudad} />
      {marcadores}
    </MapContainer>
  );
}
