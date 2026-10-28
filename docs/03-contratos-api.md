# 03 — Especificación de Contratos REST (API)

Todos los esquemas están tipados y validados en [`backend/app/esquemas.py`](../backend/app/esquemas.py). La documentación OpenAPI interactiva está disponible en `GET /docs`.

---

## 1. Endpoints Públicos (`app/routers/publico.py`)

### `GET /api/ciudades`
Devuelve las ciudades registradas para centrar el mapa y poblar el selector de ciudad.
- **Respuesta `200 OK`:**
  ```json
  [
    {
      "id": 1,
      "slug": "cuenca",
      "nombre": "Cuenca",
      "provincia": "Azuay",
      "latitud": -2.9001,
      "longitud": -79.0059,
      "zoom": 14
    }
  ]
  ```

### `GET /api/parqueos?ciudad=cuenca`
Lista los parqueaderos **activos** con su ocupación actual calculada.
- **Respuesta `200 OK`:** lista de `ParqueoSalida`.
- **Errores:** `404 Not Found` si el `slug` de ciudad no existe.

### `GET /api/parqueos/{parqueo_id}`
Detalle en tiempo real de un parqueadero activo.
- **Respuesta `200 OK`:**
  ```json
  {
    "id": 1,
    "ciudad_id": 1,
    "nombre": "Parqueadero Parque Calderón",
    "direccion": "Simón Bolívar y Luis Cordero, Centro Histórico",
    "latitud": -2.89706,
    "longitud": -79.00444,
    "capacidad": 120,
    "ocupados": 104,
    "disponibles": 16,
    "activo": true
  }
  ```
- **Errores:** `404 Not Found` si no existe o está inactivo.

---

## 2. Autenticación y Perfil (`app/routers/auth.py`)

### `POST /api/auth/login`
- **Cuerpo (`LoginEntrada`):**
  ```json
  { "usuario": "superadmin", "clave": "balzai2026" }
  ```
- **Respuesta `200 OK` (`TokenSalida`):**
  ```json
  {
    "access_token": "<jwt>",
    "token_type": "bearer",
    "expira_en": 28800,
    "rol": "superadmin",
    "usuario": "superadmin",
    "nombre": "Dirección General BalzAI",
    "parqueo_id": null
  }
  ```
- **Errores:** `401 Unauthorized` si credenciales inválidas o cuenta inactiva.

### `GET /api/auth/perfil`
- **Cabecera:** `Authorization: Bearer <token>`
- **Respuesta `200 OK` (`PerfilSalida`):** `{ id, usuario, nombre, rol, parqueo_id, activo }`.

---

## 3. Operación de Parqueaderos (`app/routers/admin.py`)

Requieren cabecera `Authorization: Bearer <token>` con rol `admin` o `superadmin`. Si la cuenta es `admin` y tiene `parqueo_id != null`, todas las rutas están restringidas a ese `parqueo_id`.

| Método y Ruta | Cuerpo | Respuesta | Códigos de Error |
| :--- | :--- | :--- | :--- |
| `GET /api/admin/parqueos` | — | `list[ParqueoSalida]` (incluye inactivos; filtrado a `parqueo_id` si aplica) | `401`, `403` |
| `POST /api/admin/parqueos` | `ParqueoCrear` | `201 ParqueoSalida` | `401`, `403` (si operador restringido), `404` (ciudad), `409` (nombre duplicado) |
| `PATCH /api/admin/parqueos/{id}` | `ParqueoActualizar` | `200 ParqueoSalida` | `401`, `403`, `404`, `409` (capacidad menor a ocupados o nombre duplicado) |
| `POST /api/admin/parqueos/{id}/movimientos` | `{"tipo": "entrada" \| "salida"}` | `201 ParqueoSalida` | `401`, `403`, `404`, `409` (parqueo lleno, vacío o inactivo) |
| `POST /api/admin/parqueos/{id}/dispositivos` | `{"nombre": "Barrera Norte"}` | `201 DispositivoCreado` (incluye `clave` en claro una sola vez) | `401`, `403`, `404` |

---

## 4. Superadministración y Analíticas (`app/routers/superadmin.py`)

Exclusivo para cuentas con `rol = "superadmin"` (`Authorization: Bearer <token>`). Cualquier cuenta con `rol = "admin"` recibe `403 Forbidden`.

### `GET /api/superadmin/analiticas?ciudad=cuenca&horas=24`
Devuelve el estado global de la aplicación, la serie de flujo horario, las métricas de tráfico/rotación por parqueadero y los últimos 25 movimientos.
- **Respuesta `200 OK` (`AnaliticasSalida`):**
  ```json
  {
    "ventana_horas": 24,
    "ciudad_filtro": "cuenca",
    "resumen": {
      "ciudades_total": 1,
      "parqueos_activos": 8,
      "parqueos_inactivos": 0,
      "capacidad_total": 1350,
      "ocupados_actuales": 729,
      "disponibles_actuales": 621,
      "porcentaje_ocupacion": 54.0,
      "movimientos_totales": 893,
      "entradas_totales": 811,
      "salidas_totales": 82,
      "movimientos_ventana": 893,
      "entradas_ventana": 811,
      "salidas_ventana": 82,
      "por_origen": { "manual": 848, "dispositivo": 45 },
      "hora_pico": { "hora": "08:00", "movimientos": 112 },
      "operadores_activos": 2,
      "dispositivos_activos": 1
    },
    "flujo_horario": [
      {
        "hora_iso": "2026-10-28T12:00:00+00:00",
        "etiqueta": "12:00",
        "entradas": 42,
        "salidas": 8,
        "flujo_neto": 34,
        "total": 50
      }
    ],
    "trafico_por_parqueo": [
      {
        "id": 1,
        "nombre": "Parqueadero Parque Calderón",
        "ciudad_id": 1,
        "ciudad_nombre": "Cuenca",
        "activo": true,
        "capacidad": 120,
        "ocupados": 104,
        "disponibles": 16,
        "porcentaje_ocupacion": 86.7,
        "entradas_totales": 116,
        "salidas_totales": 12,
        "movimientos_ventana": 128,
        "indice_rotacion": 0.97,
        "dispositivos_activos": 1,
        "operadores_asignados": 1
      }
    ],
    "movimientos_recientes": [
      {
        "id": 893,
        "parqueo_id": 1,
        "parqueo_nombre": "Parqueadero Parque Calderón",
        "tipo": "entrada",
        "origen": "dispositivo",
        "actor": "Sensor Barrera Principal Calderón",
        "creado_en": "2026-10-28T13:15:00Z"
      }
    ]
  }
  ```

### Control de Ciudades, Operadores y Sensores
- `POST /api/superadmin/ciudades` (`CiudadCrear` -> `201 CiudadSalida`)
- `PATCH /api/superadmin/ciudades/{ciudad_id}` (`CiudadActualizar` -> `200 CiudadSalida`)
- `GET /api/superadmin/operadores` (`200 list[OperadorSalida]`)
- `POST /api/superadmin/operadores` (`OperadorCrear` -> `201 OperadorSalida`)
- `PATCH /api/superadmin/operadores/{operador_id}` (`OperadorActualizar` -> `200 OperadorSalida`)
- `GET /api/superadmin/dispositivos` (`200 list[DispositivoSalida]`)
- `PATCH /api/superadmin/dispositivos/{dispositivo_id}` (`DispositivoActualizar` -> `200 DispositivoSalida`)

---

## 5. Sensores y Dispositivos IoT (`app/routers/dispositivos.py`)

### `POST /api/dispositivos/movimientos`
- **Cabecera obligatoria:** `X-Clave-Dispositivo: <clave>`
- **Cuerpo:** `{"tipo": "entrada" | "salida"}`
- **Respuesta `201 Created`:** `ParqueoSalida` con la ocupación resultante del parqueadero asociado al sensor.
- **Errores:** `401 Unauthorized` (clave ausente, inválida o dispositivo revocado), `409 Conflict` (parqueadero lleno, vacío o inactivo).
