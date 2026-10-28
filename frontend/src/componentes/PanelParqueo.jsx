import { useCallback, useEffect, useRef, useState } from "react";
import BarraOcupacion from "./BarraOcupacion.jsx";
import {
  RastreadorVelocidad,
  crearResorte,
  ligaElastica,
  proyectar,
  vibrar,
} from "../fisica.js";
import { ETIQUETAS_NIVEL, nivelOcupacion } from "../ocupacion.js";

const HISTERESIS_PX = 8;

function esVistaMovil() {
  return typeof window !== "undefined" && window.matchMedia?.("(max-width: 760px)").matches;
}

/**
 * Panel flotante con los espacios disponibles y ocupados del parqueo seleccionado.
 *
 * Implementa manipulación directa 1:1 (Pointer Events + capture), interrumpibilidad en
 * pleno vuelo, resistencia elástica en el borde (rubber-banding), proyección de momento
 * exponencial y transferencia de velocidad al resorte de cierre o asentamiento.
 */
export default function PanelParqueo({ parqueo, error, onCerrar }) {
  // Conservamos el último parqueo/error visible mientras el resorte termina de cerrar
  // para que la tarjeta salga con su contenido por el mismo camino por el que entró.
  const [visible, setVisible] = useState(parqueo || error ? { parqueo, error } : null);
  const panelRef = useRef(null);
  const resorteRef = useRef(null);
  const cerrandoRef = useRef(false);
  const onCerrarRef = useRef(onCerrar);
  onCerrarRef.current = onCerrar;

  const aplicarTransformacion = useCallback((desplazamiento) => {
    const el = panelRef.current;
    if (!el) return;
    const movil = esVistaMovil();
    const dimension = movil ? el.offsetHeight || 320 : el.offsetWidth || 360;
    const progreso = Math.max(0, Math.min(1, desplazamiento / dimension));
    // Materialización sutil: combina traslación en el eje del gesto, ligera escala y opacidad.
    const escala = 1 - progreso * 0.03;
    const opacidad = 1 - progreso * 0.25;
    el.style.transform = movil
      ? `translate3d(0, ${desplazamiento.toFixed(2)}px, 0) scale(${escala.toFixed(4)})`
      : `translate3d(${desplazamiento.toFixed(2)}px, 0, 0) scale(${escala.toFixed(4)})`;
    el.style.opacity = String(opacidad.toFixed(3));
  }, []);

  const distanciaOculto = useCallback(() => {
    const el = panelRef.current;
    if (!el) return 380;
    return esVistaMovil() ? (el.offsetHeight || 320) + 32 : (el.offsetWidth || 360) + 32;
  }, []);

  useEffect(() => {
    const resorte = crearResorte({
      valorInicial: 380,
      damping: 1.0,
      response: 0.34,
      onCambio: aplicarTransformacion,
      onReposo: () => {
        if (cerrandoRef.current) {
          cerrandoRef.current = false;
          setVisible(null);
        }
      },
    });
    resorteRef.current = resorte;
    return () => resorte.detener();
  }, [aplicarTransformacion]);

  useEffect(() => {
    if (parqueo || error) {
      const estabaOculto = !visible && !cerrandoRef.current;
      cerrandoRef.current = false;
      setVisible({ parqueo, error });

      requestAnimationFrame(() => {
        if (!resorteRef.current) return;
        if (estabaOculto) {
          resorteRef.current.fijar(distanciaOculto());
        }
        // Damping 1.0: entrada limpia y sin rebote artificial.
        resorteRef.current.irA(0, { damping: 1.0, response: 0.34 });
      });
    } else if (visible && !cerrandoRef.current) {
      cerrandoRef.current = true;
      resorteRef.current?.irA(distanciaOculto(), { damping: 1.0, response: 0.3 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parqueo, error, distanciaOculto]);

  const solicitarCierre = useCallback(
    (velocidadInicial = 0) => {
      if (cerrandoRef.current) return;
      cerrandoRef.current = true;
      vibrar(6);
      resorteRef.current?.irA(distanciaOculto(), {
        velocidad: velocidadInicial,
        damping: 1.0,
        response: 0.3,
      });
      onCerrarRef.current?.();
    },
    [distanciaOculto],
  );

  // Cerrar con Escape para accesibilidad de teclado (principio de Wayfinding / Agency).
  useEffect(() => {
    if (!parqueo && !error) return undefined;
    const alPulsarTecla = (e) => {
      if (e.key === "Escape") solicitarCierre(0);
    };
    window.addEventListener("keydown", alPulsarTecla);
    return () => window.removeEventListener("keydown", alPulsarTecla);
  }, [parqueo, error, solicitarCierre]);

  // --------------------------------------------------- manipulación directa (arrastre 1:1)
  const arrastreRef = useRef(null);

  const iniciarArrastre = (e) => {
    // No iniciar arrastre si se pulsó el botón de cerrar o un control interactivo.
    if (e.target.closest("button, a, input, select")) return;
    if (e.button !== undefined && e.button !== 0) return;

    const el = panelRef.current;
    const resorte = resorteRef.current;
    if (!el || !resorte) return;

    const movil = esVistaMovil();
    const coord = movil ? e.clientY : e.clientX;
    // Interrumpibilidad: leemos la posición viva actual del resorte en el instante del toque.
    const posicionViva = resorte.estado().valor;
    cerrandoRef.current = false;
    resorte.fijar(posicionViva);

    const rastreador = new RastreadorVelocidad();
    rastreador.registrar(posicionViva);

    arrastreRef.current = {
      pointerId: e.pointerId,
      movil,
      inicioCoord: coord,
      // Respetamos el offset exacto desde donde el usuario agarró el panel.
      desfaseAgarre: coord - posicionViva,
      comprometido: false,
      ultimoValor: posicionViva,
      rastreador,
    };

    el.setPointerCapture?.(e.pointerId);
  };

  const moverArrastre = (e) => {
    const estado = arrastreRef.current;
    if (!estado || estado.pointerId !== e.pointerId) return;

    const coord = estado.movil ? e.clientY : e.clientX;
    if (!estado.comprometido) {
      if (Math.abs(coord - estado.inicioCoord) < HISTERESIS_PX) return;
      estado.comprometido = true;
      // Reajustamos el desfase tras superar el umbral de histéresis para evitar un salto de 8px.
      estado.desfaseAgarre = coord - estado.ultimoValor;
    }

    const el = panelRef.current;
    const dimension = estado.movil ? el?.offsetHeight || 320 : el?.offsetWidth || 360;
    const crudo = coord - estado.desfaseAgarre;

    // En la dirección opuesta al cierre (< 0), aplicamos resistencia progresiva (rubber-banding).
    const posicion = crudo < 0 ? ligaElastica(crudo, dimension, 0.55) : crudo;
    estado.ultimoValor = posicion;
    estado.rastreador.registrar(posicion);
    resorteRef.current?.fijar(posicion);
  };

  const finalizarArrastre = (e) => {
    const estado = arrastreRef.current;
    if (!estado || estado.pointerId !== e.pointerId) return;
    arrastreRef.current = null;

    panelRef.current?.releasePointerCapture?.(e.pointerId);
    if (!estado.comprometido) return;

    const velocidadSalida = estado.rastreador.velocidad();
    const posicionActual = estado.ultimoValor;
    const destinoProyectado = posicionActual + proyectar(velocidadSalida, 0.998);
    const umbral = distanciaOculto() * 0.36;

    // Usamos el punto proyectado Y el signo de la velocidad para decidir cierre vs. retorno.
    const debeCerrar =
      (destinoProyectado > umbral && velocidadSalida >= -80) || velocidadSalida > 650;

    if (debeCerrar) {
      solicitarCierre(velocidadSalida);
    } else {
      // Ligero rebote (damping 0.82) solo cuando el gesto llevaba impulso real.
      const conImpulso = Math.abs(velocidadSalida) > 250;
      resorteRef.current?.irA(0, {
        velocidad: velocidadSalida,
        damping: conImpulso ? 0.82 : 1.0,
        response: 0.34,
      });
    }
  };

  if (!visible) {
    return (
      <aside className="panel panel-guia cristal" aria-label="Guía del mapa">
        <h2>Elige un parqueo</h2>
        <p>Pulsa un marcador del mapa para consultar sus espacios en tiempo real.</p>
        <p className="leyenda">El número en cada marcador muestra los espacios libres.</p>
        <ul className="leyenda-colores">
          {["libre", "medio", "lleno"].map((nivel) => (
            <li key={nivel}>
              <span className={`punto nivel-${nivel}`} /> {ETIQUETAS_NIVEL[nivel]}
            </li>
          ))}
        </ul>
      </aside>
    );
  }

  const { parqueo: actual, error: errorActual } = visible;

  if (errorActual) {
    return (
      <aside
        ref={panelRef}
        className="panel panel-detalle cristal"
        onPointerDown={iniciarArrastre}
        onPointerMove={moverArrastre}
        onPointerUp={finalizarArrastre}
        onPointerCancel={finalizarArrastre}
      >
        <div className="tirador" aria-hidden="true" />
        <BotonCerrar onClick={() => solicitarCierre(0)} />
        <p className="error">{errorActual}</p>
      </aside>
    );
  }

  const nivel = nivelOcupacion(actual);
  const porcentaje = Math.round((actual.ocupados / actual.capacidad) * 100);

  return (
    <aside
      ref={panelRef}
      className="panel panel-detalle cristal"
      aria-live="polite"
      onPointerDown={iniciarArrastre}
      onPointerMove={moverArrastre}
      onPointerUp={finalizarArrastre}
      onPointerCancel={finalizarArrastre}
    >
      <div className="tirador" aria-hidden="true" />
      <BotonCerrar onClick={() => solicitarCierre(0)} />
      <span className={`etiqueta nivel-${nivel}`}>{ETIQUETAS_NIVEL[nivel]}</span>
      <h2>{actual.nombre}</h2>
      {actual.direccion && <p className="direccion">{actual.direccion}</p>}

      <div className="cifras">
        <div className="cifra">
          <strong className={`texto-${nivel}`}>{actual.disponibles}</strong>
          <span>disponibles</span>
        </div>
        <div className="cifra">
          <strong>{actual.ocupados}</strong>
          <span>ocupados</span>
        </div>
      </div>

      <BarraOcupacion parqueo={actual} />
      <div className="pie-capacidad">
        <span>Capacidad total: {actual.capacidad} espacios</span>
        <span>{porcentaje}% ocupado</span>
      </div>
    </aside>
  );
}

function BotonCerrar({ onClick }) {
  return (
    <button type="button" className="cerrar" onClick={onClick} aria-label="Cerrar panel">
      ×
    </button>
  );
}
