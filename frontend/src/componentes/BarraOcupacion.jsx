import { useEffect, useRef } from "react";
import { crearResorte } from "../fisica.js";
import { nivelOcupacion } from "../ocupacion.js";

/**
 * Barra horizontal de ocupación.
 * Anima con `transform: scaleX()` mediante un resorte críticamente amortiguado (damping 1.0)
 * para mantenerse en el compositor y ser interrumpible si entran varios vehículos seguidos.
 */
export default function BarraOcupacion({ parqueo }) {
  const razon = Math.max(0, Math.min(1, parqueo.ocupados / parqueo.capacidad));
  const porcentaje = Math.round(razon * 100);
  const rellenoRef = useRef(null);
  const resorteRef = useRef(null);

  useEffect(() => {
    const resorte = crearResorte({
      valorInicial: razon,
      damping: 1.0,
      response: 0.38,
      precision: 0.002,
      onCambio: (v) => {
        if (rellenoRef.current) {
          rellenoRef.current.style.transform = `scaleX(${Math.max(0, Math.min(1, v))})`;
        }
      },
    });
    resorteRef.current = resorte;
    return () => resorte.detener();
    // Solo se crea al montar; los cambios de `razon` redirigen el resorte en curso.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    resorteRef.current?.irA(razon, { damping: 1.0, response: 0.38 });
  }, [razon]);

  return (
    <div
      className="barra"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={parqueo.capacidad}
      aria-valuenow={parqueo.ocupados}
      aria-label={`${porcentaje}% ocupado`}
    >
      <div
        ref={rellenoRef}
        className={`barra-relleno nivel-${nivelOcupacion(parqueo)}`}
        style={{ transform: `scaleX(${razon})` }}
      />
    </div>
  );
}
