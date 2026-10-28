/** Clasifica un parqueo según su disponibilidad (colores del mapa y del panel). */
export function nivelOcupacion({ capacidad, disponibles, activo = true }) {
  if (!activo) return "inactivo";
  if (disponibles <= 0) return "lleno";
  if (disponibles / capacidad <= 0.2) return "medio"; // quedan pocos espacios
  return "libre";
}

export const ETIQUETAS_NIVEL = {
  libre: "Disponible",
  medio: "Pocos espacios",
  lleno: "Lleno",
  inactivo: "Inactivo",
};
