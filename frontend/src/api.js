/**
 * Cliente HTTP de la API. Todas las rutas son relativas (/api/...):
 * en desarrollo las atiende el proxy de Vite; en producción, VITE_API_URL.
 */

const BASE = import.meta.env.VITE_API_URL ?? "";
const CLAVE_TOKEN = "parqueos.token";
const CLAVE_SESION = "parqueos.sesion";

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

// ----------------------------------------------------------------- autenticación

export async function iniciarSesion(usuario, clave) {
  const respuesta = await solicitar("/api/auth/login", {
    metodo: "POST",
    cuerpo: { usuario, clave },
  });
  const sesion = {
    token: respuesta.access_token,
    rol: respuesta.rol ?? "admin",
    usuario: respuesta.usuario ?? usuario,
    nombre: respuesta.nombre ?? null,
    parqueo_id: respuesta.parqueo_id ?? null,
  };
  sessionStorage.setItem(CLAVE_TOKEN, sesion.token);
  sessionStorage.setItem(CLAVE_SESION, JSON.stringify(sesion));
  return sesion;
}

export function sesionGuardada() {
  try {
    const crudo = sessionStorage.getItem(CLAVE_SESION);
    if (crudo) return JSON.parse(crudo);
  } catch {
    // Ignorar JSON corrupto.
  }
  const token = sessionStorage.getItem(CLAVE_TOKEN);
  return token ? { token, rol: "admin", usuario: "", nombre: null, parqueo_id: null } : null;
}

export const tokenGuardado = () => sesionGuardada()?.token ?? null;

export function cerrarSesion() {
  sessionStorage.removeItem(CLAVE_TOKEN);
  sessionStorage.removeItem(CLAVE_SESION);
}

export const obtenerPerfil = (token) => solicitar("/api/auth/perfil", { token });

// ----------------------------------------------------------------- operación de parqueaderos (/api/admin)

export const admin = {
  listarParqueos: (token) => solicitar("/api/admin/parqueos", { token }),
  crearParqueo: (token, datos) =>
    solicitar("/api/admin/parqueos", { metodo: "POST", cuerpo: datos, token }),
  actualizarParqueo: (token, id, cambios) =>
    solicitar(`/api/admin/parqueos/${id}`, { metodo: "PATCH", cuerpo: cambios, token }),
  registrarMovimiento: (token, id, tipo) =>
    solicitar(`/api/admin/parqueos/${id}/movimientos`, { metodo: "POST", cuerpo: { tipo }, token }),
  crearDispositivo: (token, parqueoId, nombre) =>
    solicitar(`/api/admin/parqueos/${parqueoId}/dispositivos`, {
      metodo: "POST",
      cuerpo: { nombre },
      token,
    }),
};

// ----------------------------------------------------------------- superadministración (/api/superadmin)

export const superadmin = {
  obtenerAnaliticas: (token, { ciudad = "", horas = 24 } = {}) => {
    const params = new URLSearchParams();
    if (ciudad) params.set("ciudad", ciudad);
    if (horas) params.set("horas", String(horas));
    const qs = params.toString();
    return solicitar(`/api/superadmin/analiticas${qs ? `?${qs}` : ""}`, { token });
  },
  crearCiudad: (token, datos) =>
    solicitar("/api/superadmin/ciudades", { metodo: "POST", cuerpo: datos, token }),
  actualizarCiudad: (token, id, cambios) =>
    solicitar(`/api/superadmin/ciudades/${id}`, { metodo: "PATCH", cuerpo: cambios, token }),
  listarOperadores: (token) => solicitar("/api/superadmin/operadores", { token }),
  crearOperador: (token, datos) =>
    solicitar("/api/superadmin/operadores", { metodo: "POST", cuerpo: datos, token }),
  actualizarOperador: (token, id, cambios) =>
    solicitar(`/api/superadmin/operadores/${id}`, { metodo: "PATCH", cuerpo: cambios, token }),
  listarDispositivos: (token) => solicitar("/api/superadmin/dispositivos", { token }),
  actualizarDispositivo: (token, id, cambios) =>
    solicitar(`/api/superadmin/dispositivos/${id}`, { metodo: "PATCH", cuerpo: cambios, token }),
};
