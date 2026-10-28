/**
 * Cliente mínimo de la API. Todas las rutas son relativas (/api/...):
 * en desarrollo las atiende el proxy de Vite; en producción, VITE_API_URL.
 */

const BASE = import.meta.env.VITE_API_URL ?? "";
const CLAVE_TOKEN = "parqueos.token";

export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje);
    this.estado = estado;
  }
}

async function solicitar(ruta, { metodo = "GET", cuerpo, token } = {}) {
  const cabeceras = { Accept: "application/json" };
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  if (token) cabeceras.Authorization = `Bearer ${token}`;

  let respuesta;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new ErrorApi("No se pudo conectar con el servidor.", 0);
  }

  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    throw new ErrorApi(mensajeDeError(datos, respuesta.status), respuesta.status);
  }
  return datos;
}

/** FastAPI devuelve `detail` como texto (errores de negocio) o como lista (validación 422). */
function mensajeDeError(datos, estado) {
  const detalle = datos?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle) && detalle.length > 0) {
    return detalle.map((e) => `${e.loc?.at(-1) ?? "dato"}: ${e.msg}`).join(" · ");
  }
  return `Error inesperado (${estado}).`;
}

// ----------------------------------------------------------------- lectura pública

export const obtenerCiudades = () => solicitar("/api/ciudades");

export const obtenerParqueos = (ciudadSlug) =>
  solicitar(`/api/parqueos${ciudadSlug ? `?ciudad=${encodeURIComponent(ciudadSlug)}` : ""}`);

export const obtenerParqueo = (id) => solicitar(`/api/parqueos/${id}`);

// ----------------------------------------------------------------- administración

export async function iniciarSesion(usuario, clave) {
  const { access_token } = await solicitar("/api/auth/login", {
    metodo: "POST",
    cuerpo: { usuario, clave },
  });
  sessionStorage.setItem(CLAVE_TOKEN, access_token);
  return access_token;
}

export const tokenGuardado = () => sessionStorage.getItem(CLAVE_TOKEN);
export const cerrarSesion = () => sessionStorage.removeItem(CLAVE_TOKEN);

export const admin = {
  listarParqueos: (token) => solicitar("/api/admin/parqueos", { token }),
  crearParqueo: (token, datos) =>
    solicitar("/api/admin/parqueos", { metodo: "POST", cuerpo: datos, token }),
  actualizarParqueo: (token, id, cambios) =>
    solicitar(`/api/admin/parqueos/${id}`, { metodo: "PATCH", cuerpo: cambios, token }),
  registrarMovimiento: (token, id, tipo) =>
    solicitar(`/api/admin/parqueos/${id}/movimientos`, { metodo: "POST", cuerpo: { tipo }, token }),
};
