/**
 * Primitivas de movimiento físico e interacción directa (inspiradas en Apple WWDC
 * "Designing Fluid Interfaces"):
 *  - Resortes parametrizados por `damping` (amortiguación) y `response` (respuesta en s).
 *  - Siempre animan desde el valor de presentación actual y conservan la velocidad
 *    al re-apuntar o interrumpir a mitad de vuelo.
 *  - Proyección exponencial de momento (`proyectar`) y bordes elásticos (`ligaElastica`).
 *  - Respeta `prefers-reduced-motion: reduce`.
 */

export function movimientoReducido() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Proyecta dónde terminaría un gesto si continuara desacelerando libremente.
 * Fórmula de Apple: (v / 1000) * d / (1 - d), con velocidad en px/s.
 */
export function proyectar(velocidadInicial, tasaDesaceleracion = 0.998) {
  return ((velocidadInicial / 1000) * tasaDesaceleracion) / (1 - tasaDesaceleracion);
}

/**
 * Resistencia progresiva ("rubber-banding") al arrastrar más allá de un límite.
 */
export function ligaElastica(exceso, dimension, constante = 0.55) {
  if (dimension <= 0 || exceso === 0) return 0;
  return (exceso * dimension * constante) / (dimension + constante * Math.abs(exceso));
}

/**
 * Calcula la velocidad instantánea (px/s) de los últimos ~100 ms de un arrastre
 * para entregársela sin costura al resorte en `pointerup`.
 */
export class RastreadorVelocidad {
  constructor() {
    this.muestras = [];
  }

  registrar(posicion, tiempo = performance.now()) {
    this.muestras.push({ posicion, tiempo });
    const corte = tiempo - 100;
    while (this.muestras.length > 2 && this.muestras[0].tiempo < corte) {
      this.muestras.shift();
    }
  }

  velocidad(tiempoActual = performance.now()) {
    const recientes = this.muestras.filter((m) => tiempoActual - m.tiempo <= 120);
    if (recientes.length < 2) return 0;
    const primera = recientes[0];
    const ultima = recientes[recientes.length - 1];
    const dt = (ultima.tiempo - primera.tiempo) / 1000;
    if (dt <= 0.001) return 0;
    return (ultima.posicion - primera.posicion) / dt;
  }

  limpiar() {
    this.muestras.length = 0;
  }
}

/**
 * Crea un resorte 1D sincronizado con `requestAnimationFrame`.
 *
 * - `damping`: 1.0 = críticamente amortiguado (sin rebote, por defecto);
 *              ~0.8 = con rebote sutil para gestos que traen impulso.
 * - `response`: rapidez de respuesta en segundos (típicamente 0.30–0.40).
 */
export function crearResorte({
  valorInicial = 0,
  damping = 1.0,
  response = 0.36,
  precision = 0.4,
  onCambio,
  onReposo,
}) {
  let valor = valorInicial;
  let destino = valorInicial;
  let velocidad = 0;
  let amortiguacion = damping;
  let respuesta = response;
  let rafId = null;
  let ultimoTiempo = null;

  const detenerRaf = () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    ultimoTiempo = null;
  };

  const paso = (ahora) => {
    if (ultimoTiempo === null) ultimoTiempo = ahora;
    // Acotamos dt para evitar saltos si la pestaña estuvo en segundo plano.
    const dt = Math.min((ahora - ultimoTiempo) / 1000, 1 / 30);
    ultimoTiempo = ahora;

    if (dt > 0) {
      const omega = (2 * Math.PI) / Math.max(0.05, respuesta);
      const rigidez = omega * omega;
      const friccion = 2 * amortiguacion * omega;

      // Sub-pasos de 4 ms para estabilidad numérica incluso con respuestas rápidas.
      const subPasos = Math.max(1, Math.ceil(dt / 0.004));
      const h = dt / subPasos;
      for (let i = 0; i < subPasos; i += 1) {
        const desplazamiento = valor - destino;
        const aceleracion = -rigidez * desplazamiento - friccion * velocidad;
        velocidad += aceleracion * h;
        valor += velocidad * h;
      }
    }

    const enReposo =
      Math.abs(valor - destino) <= precision && Math.abs(velocidad) <= precision * 6;

    if (enReposo) {
      valor = destino;
      velocidad = 0;
      detenerRaf();
      onCambio?.(valor);
      onReposo?.(valor);
      return;
    }

    onCambio?.(valor);
    rafId = requestAnimationFrame(paso);
  };

  return {
    /** Fija inmediatamente el valor en pantalla (p. ej. durante seguimiento 1:1 con el dedo). */
    fijar(nuevoValor, nuevaVelocidad = 0) {
      detenerRaf();
      valor = nuevoValor;
      destino = nuevoValor;
      velocidad = nuevaVelocidad;
      onCambio?.(valor);
    },

    /**
     * Anima hacia `nuevoDestino` partiendo del valor y la velocidad actuales en pantalla.
     * Nunca reinicia desde cero: si se llama en pleno vuelo, redirige con suavidad.
     */
    irA(nuevoDestino, opciones = {}) {
      destino = nuevoDestino;
      if (opciones.velocidad !== undefined) velocidad = opciones.velocidad;
      if (opciones.damping !== undefined) amortiguacion = opciones.damping;
      if (opciones.response !== undefined) respuesta = opciones.response;

      if (movimientoReducido()) {
        detenerRaf();
        valor = destino;
        velocidad = 0;
        onCambio?.(valor);
        onReposo?.(valor);
        return;
      }

      if (rafId === null) {
        ultimoTiempo = null;
        rafId = requestAnimationFrame(paso);
      }
    },

    detener() {
      detenerRaf();
    },

    estado() {
      return { valor, destino, velocidad, activo: rafId !== null };
    },
  };
}

/** Feedback háptico discreto en el mismo frame del evento causal (si el dispositivo lo soporta). */
export function vibrar(patron = 8) {
  try {
    navigator?.vibrate?.(patron);
  } catch {
    // Ignorar en navegadores o contextos que no admiten vibración.
  }
}
