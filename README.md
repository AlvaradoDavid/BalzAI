# Parqueos Cuenca (BalzAI) — Plataforma de Ocupación y Analíticas en Tiempo Real

Aplicación web para consultar en un mapa los puntos de parqueo de Cuenca (Ecuador) con sus **espacios disponibles** y **ocupados** en tiempo real, alimentada por dueños/operadores de parqueaderos y sensores IoT de acceso, y gobernada por una consola superior de **Superadministración y Analíticas de Flujo y Tráfico**.

---

## Documentación SDD (Spec-Driven Development)

Toda la especificación funcional, arquitectónica, de contratos y de hoja de ruta para continuar el proyecto en sesiones futuras se encuentra en la carpeta [`docs/`](./docs/00-indice-sdd.md):

1. [**`docs/00-indice-sdd.md`**](./docs/00-indice-sdd.md) — Índice Maestro SDD, glosario del dominio y guía de inicio rápido para próximas sesiones.
2. [**`docs/01-especificacion-funcional-y-roles.md`**](./docs/01-especificacion-funcional-y-roles.md) — Perfiles de usuario (`Público`, `Sensor IoT`, `Operador / Dueño de Parqueadero`, `Superadministrador de la App`), matriz RBAC y reglas de negocio.
3. [**`docs/02-arquitectura-y-modelo-datos.md`**](./docs/02-arquitectura-y-modelo-datos.md) — Diagramas Mermaid de arquitectura y ERD, cálculo de ocupación por eventos, concurrencia atómica y seguridad.
4. [**`docs/03-contratos-api.md`**](./docs/03-contratos-api.md) — Contratos detallados de todos los endpoints REST (`/api`, `/api/auth`, `/api/admin`, `/api/superadmin`, `/api/dispositivos`).
5. [**`docs/04-especificacion-frontend-apple-design.md`**](./docs/04-especificacion-frontend-apple-design.md) — Rutas React, sistema físico de resortes (`fisica.js`), materiales translúcidos y accesibilidad.
6. [**`docs/05-pruebas-operacion-y-roadmap.md`**](./docs/05-pruebas-operacion-y-roadmap.md) — Catálogo de las 49 pruebas automatizadas (`pytest`), paso a PostgreSQL y hoja de ruta evolutiva.

---

## Perfiles de usuario

| Perfil | Ruta Web | Credenciales de prueba (desarrollo) | Alcance |
| :--- | :--- | :--- | :--- |
| **Ciudadano / Conductor (Público)** | `/` | Sin cuenta | Consulta el mapa interactivo y los espacios libres/ocupados de cada parqueadero activo. |
| **Operador / Dueño de Parqueadero (`admin`)** | `/admin` | `admin` / `parqueos2026` *(general)*<br/>`guardia_calderon` / `parqueos2026` *(solo Parque Calderón)* | Registra entradas y salidas manuales y gestiona los datos de su(s) parqueadero(s) asignado(s). |
| **Superadministrador de la App (`superadmin`)** | `/superadmin` | `superadmin` / `balzai2026` | Control total de la aplicación, analíticas globales, flujo y tráfico por hora, rotación, gestión de ciudades, operadores y sensores IoT. |
| **Sensor / Barrera IoT (`dispositivo`)** | `POST /api/dispositivos/movimientos` | `X-Clave-Dispositivo: sensor-demo-cuenca` | Reporta entradas y salidas automáticas de su parqueadero asociado. |

---

## Ejecución local rápida

### 1. Backend (FastAPI)

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
- Documentación interactiva OpenAPI: `http://127.0.0.1:8000/docs`

### 2. Frontend (React + Vite)

```powershell
cd frontend
npm run dev
```
- Mapa público: `http://localhost:5173/`
- Panel de operadores / dueños de parqueadero: `http://localhost:5173/admin`
- Consola de Superadministrador y Analíticas: `http://localhost:5173/superadmin`

### 3. Pruebas automatizadas (49 pruebas)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```
