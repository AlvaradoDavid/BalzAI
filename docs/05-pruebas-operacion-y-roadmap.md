# 05 — Especificación de Pruebas, Operación y Hoja de Ruta

## 1. Suite de pruebas automatizadas (`backend/tests/`)

La suite cuenta con **49 pruebas automatizadas** en `pytest` que se ejecutan sobre bases SQLite temporales aisladas por prueba (`conftest.py`):

### 1.1. `tests/test_ocupacion.py` (12 pruebas)
- Parqueadero sin movimientos inicia con ocupación `0`.
- Ocupación calculada exactamente como `entradas − salidas`.
- Movimientos manuales y de dispositivo suman en el mismo conteo.
- Listado calcula cada parqueadero de forma independiente.
- Prohibición de superar la capacidad máxima (`409 Conflict`) tanto para origen `manual` como `dispositivo`.
- Prohibición de ocupación negativa al dar salida en parqueadero vacío (`409 Conflict`) para ambos orígenes.
- Parqueadero inactivo rechaza movimientos (`409 Conflict`).
- Prohibición de reducir la capacidad por debajo de los vehículos actualmente estacionados.
- **Prueba de estrés concurrente:** 20 hilos intentando entrar simultáneamente a un parqueadero de capacidad `3` -> exactamente `3` entradas tienen éxito y `17` reciben `409 Conflict`.

### 1.2. `tests/test_acceso.py` (26 pruebas)
- Lectura pública de ciudades, listado de parqueaderos y detalle sin autenticación.
- Ocultamiento de parqueaderos inactivos al público mientras siguen visibles en administración.
- Login válido e inválido (usuario inexistente o clave errónea -> `401`).
- Rechazo (`401`) de peticiones sin token o con token inválido/expirado en todas las rutas de escritura.
- Rechazo (`403`) de tokens sin rol válido.
- Aislamiento estricto entre tokens de administrador y claves `X-Clave-Dispositivo`.
- Revocación inmediata de dispositivos inactivos (`401`).

### 1.3. `tests/test_superadmin.py` (11 pruebas)
- Login de `superadmin` devuelve `rol = "superadmin"`.
- Rechazo (`401` sin token y `403 Forbidden` con token de operador `admin`) en todas las rutas de `/api/superadmin/*`.
- El `superadmin` también puede operar rutas de `/api/admin/*`.
- Exactitud matemática de `/api/superadmin/analiticas`: resumen global, flujo horario, desglose `manual` vs `dispositivo`, tráfico por parqueadero y bitácora de movimientos recientes.
- Creación de nuevas ciudades desde `/api/superadmin/ciudades` y aparición inmediata en `/api/ciudades`.
- **Aislamiento de operador asignado a un parqueadero (`parqueo_id != null`):** solo ve su parqueadero en `GET /api/admin/parqueos`, puede operar el suyo (`201`), y recibe `403 Forbidden` si intenta operar otro parqueadero o crear uno nuevo.
- Protección contra auto-desactivación del propio `superadmin` (`409 Conflict`).

---

## 2. Operación y despliegue en producción

### 2.1. Variables de entorno (`backend/.env`)
```env
ENTORNO=produccion
DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/parqueos
JWT_SECRETO=<generar con: python -c "import secrets; print(secrets.token_urlsafe(48))">
JWT_MINUTOS_EXPIRACION=480
CORS_ORIGENES=["https://parqueos.tudominio.ec"]
CARGAR_DATOS_EJEMPLO=false
```

### 2.2. Creación de cuentas por CLI en producción
```powershell
cd backend
# Crear un Superadministrador de la aplicación:
python -m app.crear_admin director_movilidad superadmin

# Crear un Operador / Dueño de parqueadero:
python -m app.crear_admin operador_centro admin
```

---

## 3. Hoja de ruta evolutiva (Backlog SDD para próximas sesiones)

### Fase 2 — Tiempo real push y reportería exportable
- **SSE / WebSockets en vivo:** notificar instantáneamente al mapa público y a la consola `/superadmin` cuando entra o sale un vehículo sin esperar el ciclo de refresco de 15 s.
- **Exportación de reportes:** endpoint `/api/superadmin/analiticas/exportar.csv` para descargar el historial de flujo y rotación por rango de fechas.

### Fase 3 — Inteligencia operativa (BalzAI)
- **Predicción de ocupación:** modelo ligero sobre la serie histórica de `movimientos` por día de la semana y hora para estimar probabilidad de encontrar espacio libre en los próximos 30–60 minutos.
- **Integración con cámaras LPR / ANPR:** adaptador de webhook hacia `/api/dispositivos/movimientos` con metadatos opcionales de lectura de borde.

### Fase 4 — Experiencia ciudadana extendida
- **Navegación hacia el parqueadero:** enlace directo desde `PanelParqueo` para abrir la ruta hacia las coordenadas del parqueadero.
- **Alertas de saturación para el Superadmin:** indicadores automáticos cuando un parqueadero permanece al 100% durante más de $N$ minutos o cuando un sensor IoT deja de reportar latidos (*heartbeat*).
