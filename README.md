# Parqueos Cuenca — MVP de ocupación en tiempo real

Aplicación web para consultar en un mapa los puntos de parqueo de Cuenca (Ecuador) y ver al instante sus **espacios disponibles** y **ocupados**, calculados exclusivamente a partir del conteo de entradas y salidas de vehículos. Diseñada desde el inicio para escalar a nuevas ciudades del país agregando datos, sin cambios de código.

---

## Decisiones tecnológicas

- **Backend en Python + FastAPI:** elegido por su alto rendimiento asíncrono, validación declarativa con Pydantic v2 y generación automática de documentación OpenAPI (`/docs`), lo que permite servir con un único contrato tanto a la aplicación web como a sensores/barreras de acceso.
- **Frontend en React + Leaflet con OpenStreetMap:** elegido porque Leaflet es ligero y de código abierto y las teselas de OpenStreetMap son gratuitas y no requieren clave de API ni tarjeta de crédito, evitando costos por visualización al escalar a más ciudades.
- **Interfaz y movimiento fluido (Apple Design):** capas flotantes translúcidas (`backdrop-filter`) sobre el mapa, tipografía del sistema con *optical sizing*, *tracking* por tamaño y cifras tabulares (`tabular-nums`), respuesta inmediata en `pointer-down` (`:active`) y tarjeta de detalle con seguimiento 1:1 del puntero, bordes elásticos (*rubber-banding*), proyección exponencial de momento y resortes físicos interrumpibles (`damping` + `response`), respetando `prefers-reduced-motion` y `prefers-reduced-transparency`.

---

## Estructura de carpetas

```text
parqueos-cuenca/
├── README.md
├── .gitignore
├── backend/
│   ├── .env.example
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # Punto de entrada FastAPI y ciclo de vida
│   │   ├── config.py             # Configuración por variables de entorno
│   │   ├── database.py           # Motor SQLAlchemy (SQLite / PostgreSQL)
│   │   ├── models.py             # Esquema relacional (Ciudad, Parqueo, Movimiento, Administrador, Dispositivo)
│   │   ├── esquemas.py           # Contratos Pydantic de entrada y salida
│   │   ├── seguridad.py          # PBKDF2-HMAC-SHA256, JWT y claves SHA-256 de sensores
│   │   ├── dependencias.py       # Control de acceso por rol (admin JWT y dispositivo API key)
│   │   ├── datos_ejemplo.py      # Carga inicial de datos de Cuenca si la base está vacía
│   │   ├── crear_admin.py        # CLI para crear/actualizar administradores en producción
│   │   ├── datos/
│   │   │   └── datos_ejemplo.json
│   │   ├── routers/
│   │   │   ├── publico.py        # GET /api/ciudades, /api/parqueos, /api/parqueos/{id}
│   │   │   ├── auth.py           # POST /api/auth/login
│   │   │   ├── admin.py          # Gestión de parqueos y registro manual de movimientos
│   │   │   └── dispositivos.py   # POST /api/dispositivos/movimientos (sensores/barreras)
│   │   └── servicios/
│   │       ├── errores.py        # Excepciones de dominio traducidas a HTTP (404, 409)
│   │       └── ocupacion.py      # Cálculo de ocupación y escritura atómica con validación de capacidad
│   └── tests/
│       ├── conftest.py
│       ├── test_ocupacion.py     # Pruebas de conteo, límites de capacidad y concurrencia
│       └── test_acceso.py        # Pruebas de endpoints, roles, JWT y claves de dispositivos
└── frontend/
    ├── .env.example
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js                # Cliente HTTP hacia /api
        ├── ocupacion.js          # Clasificación por nivel de disponibilidad
        ├── fisica.js             # Resortes (damping/response), proyección de momento y rubber-banding
        ├── estilos.css           # Materiales translúcidos, tipografía óptica y accesibilidad
        ├── componentes/
        │   ├── MapaParqueos.jsx
        │   ├── PanelParqueo.jsx
        │   ├── BarraOcupacion.jsx
        │   └── FormularioParqueo.jsx
        └── paginas/
            ├── PaginaMapa.jsx    # Vista pública (solo lectura)
            └── PaginaAdmin.jsx   # Panel mínimo de administración
```

---

## Modelo de datos y cálculo de ocupación

La ocupación **no se almacena en una columna**: se calcula siempre a partir de la tabla `movimientos` ($\text{ocupados} = \text{entradas} - \text{salidas}$, $\text{disponibles} = \text{capacidad} - \text{ocupados}$), garantizando una única fuente de verdad auditable.

- **`ciudades`**: `id`, `slug`, `nombre`, `provincia`, `latitud`, `longitud`, `zoom`. Agregar una ciudad a la plataforma consiste únicamente en insertar una fila en esta tabla.
- **`parqueos`**: `id`, `ciudad_id`, `nombre`, `direccion`, `latitud`, `longitud`, `capacidad` (`> 0`), `activo`, `creado_en`.
- **`movimientos`**: `id`, `parqueo_id`, `tipo` (`entrada` | `salida`), `origen` (`manual` | `dispositivo`), `administrador_id`, `dispositivo_id`, `creado_en`. Índice compuesto `(parqueo_id, tipo)` para calcular la ocupación leyendo únicamente el índice.
- **`administradores`**: `id`, `usuario`, `clave_hash` (PBKDF2-HMAC-SHA256), `activo`, `creado_en`.
- **`dispositivos`**: `id`, `nombre`, `parqueo_id`, `clave_hash` (SHA-256), `activo`, `creado_en`. Cada sensor solo puede registrar movimientos en el parqueo al que pertenece.

### Garantía de capacidad ($0 \le \text{ocupados} \le \text{capacidad}$)

En `app/servicios/ocupacion.py`, tanto los registros manuales como los provenientes de sensores ejecutan un `INSERT INTO movimientos ... SELECT ... WHERE <regla de capacidad>` dentro de la misma sentencia SQL (acompañado de `SELECT ... FOR UPDATE` en PostgreSQL). Si un parqueo está lleno (`ocupados == capacidad`) y llega una entrada, o está vacío (`ocupados == 0`) y llega una salida, la sentencia inserta `0` filas y la API responde `409 Conflict`, impidiendo estados negativos o sobrecupo incluso ante peticiones simultáneas.

---

## Endpoints REST

| Método | Ruta | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/ciudades` | Público | Lista las ciudades activas con coordenadas y zoom inicial. |
| `GET` | `/api/parqueos?ciudad=cuenca` | Público | Lista los parqueos activos con `capacidad`, `ocupados` y `disponibles`. |
| `GET` | `/api/parqueos/{id}` | Público | Detalle de ocupación en tiempo real de un parqueo activo. |
| `POST` | `/api/auth/login` | Público | Autentica a un administrador y devuelve un token JWT Bearer. |
| `GET` | `/api/admin/parqueos` | Admin (`Bearer`) | Lista todos los parqueos (incluidos inactivos) para el panel. |
| `POST` | `/api/admin/parqueos` | Admin (`Bearer`) | Crea un nuevo parqueo en una ciudad. |
| `PATCH` | `/api/admin/parqueos/{id}` | Admin (`Bearer`) | Actualiza nombre, dirección, coordenadas, capacidad o estado `activo`. |
| `POST` | `/api/admin/parqueos/{id}/movimientos` | Admin (`Bearer`) | Registra manualmente una `entrada` o `salida` (`409` si viola capacidad). |
| `POST` | `/api/admin/parqueos/{id}/dispositivos` | Admin (`Bearer`) | Crea una clave para un sensor de acceso asociado a ese parqueo. |
| `POST` | `/api/dispositivos/movimientos` | Dispositivo (`X-Clave-Dispositivo`) | Registra una `entrada` o `salida` enviada por un sensor físico. |

---

## Ejecución local

### 1. Backend (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Al arrancar por primera vez con la base vacía, se cargan automáticamente 8 parqueos de ejemplo de Cuenca, un usuario administrador y un sensor de demostración:

- **Usuario administrador:** `admin`
- **Contraseña:** `parqueos2026`
- **Clave de sensor de prueba (Parqueadero Parque Calderón):** `sensor-demo-cuenca`
- **Documentación interactiva OpenAPI:** `http://127.0.0.1:8000/docs`

Ejemplo de registro desde un sensor o barrera de acceso:

```bash
curl -X POST http://127.0.0.1:8000/api/dispositivos/movimientos \
  -H "Content-Type: application/json" \
  -H "X-Clave-Dispositivo: sensor-demo-cuenca" \
  -d '{"tipo": "entrada"}'
```

### 2. Frontend (React + Vite)

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173`:
- **`/` (Mapa):** vista pública de lectura con los marcadores de Cuenca y panel de espacios disponibles/ocupados al seleccionar un parqueo.
- **`/admin` (Administración):** vista protegida para registrar entradas/salidas con un clic y crear o editar parqueos.

### 3. Pruebas automatizadas

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

### 4. Paso a PostgreSQL en producción

1. Descomenta `psycopg[binary]==3.2.*` en `backend/requirements.txt` e instálalo.
2. Define en `backend/.env`:
   ```env
   ENTORNO=produccion
   DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/parqueos
   JWT_SECRETO=<cadena-aleatoria-segura>
   CARGAR_DATOS_EJEMPLO=false
   ```
3. Crea el primer administrador con `python -m app.crear_admin <usuario>`.
