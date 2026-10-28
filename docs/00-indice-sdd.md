# 00 — Índice Maestro SDD (Spec-Driven Development)

> **Proyecto:** Parqueos Cuenca / Plataforma Nacional de Parqueos (BalzAI)  
> **Versión actual:** `0.2.0`  
> **Repositorio:** `https://github.com/AlvaradoDavid/BalzAI.git`

---

## 1. Propósito de esta documentación SDD

Este directorio contiene la **Especificación Viva del Sistema** bajo la metodología **SDD (*Spec-Driven Development* / Desarrollo Guiado por Especificaciones)**. Su objetivo es que cualquier desarrollador o agente de IA en sesiones futuras comprenda de inmediato:

1. **Qué hace el sistema y por qué** (reglas de negocio, invariantes y límites de alcance).
2. **Quiénes interactúan con él** (jerarquía de 4 actores: Público, Sensor IoT, Operador/Dueño de Parqueadero y Superadministrador de la Aplicación).
3. **Cómo está construido** (modelos de datos, contratos de API, motor físico del frontend y suite de pruebas).
4. **Qué sigue en la hoja de ruta** y cómo extender el sistema sin romper sus invariantes.

---

## 2. Mapa de documentos SDD

| Archivo | Documento SDD | Contenido principal |
| :--- | :--- | :--- |
| [`00-indice-sdd.md`](./00-indice-sdd.md) | **Índice Maestro y Glosario** | Metodología SDD, glosario ubicuo, guía rápida para futuras sesiones. |
| [`01-especificacion-funcional-y-roles.md`](./01-especificacion-funcional-y-roles.md) | **Especificación Funcional y RBAC** | Perfiles de usuario (`Público`, `Sensor`, `Operador`, `Superadmin`), historias de usuario y reglas de negocio `RN-01`..`RN-08`. |
| [`02-arquitectura-y-modelo-datos.md`](./02-arquitectura-y-modelo-datos.md) | **Arquitectura y Modelo de Datos** | Diagramas Mermaid de arquitectura y ERD, cálculo de ocupación por eventos, concurrencia atómica y seguridad. |
| [`03-contratos-api.md`](./03-contratos-api.md) | **Especificación de Contratos REST** | Endpoints públicos, de autenticación, de operación (`/api/admin`), de superadministración (`/api/superadmin`) y de sensores (`/api/dispositivos`). |
| [`04-especificacion-frontend-apple-design.md`](./04-especificacion-frontend-apple-design.md) | **Especificación de Frontend y UX** | Rutas (`/`, `/admin`, `/superadmin`), física de resortes (`fisica.js`), materiales translúcidos y accesibilidad. |
| [`05-pruebas-operacion-y-roadmap.md`](./05-pruebas-operacion-y-roadmap.md) | **Pruebas, Operación y Hoja de Ruta** | Cobertura de las 49 pruebas en `pytest`, comandos de operación, migración a PostgreSQL y siguientes fases. |

---

## 3. Glosario del lenguaje ubicuo

- **Ciudad (`Ciudad`):** unidad geográfica (p. ej. Cuenca, Quito, Loja) con coordenadas centrales y nivel de zoom inicial. Agregar una ciudad es una operación de datos, no de código.
- **Parqueo / Parqueadero (`Parqueo`):** establecimiento de estacionamiento con una capacidad total fija (`capacidad > 0`), coordenadas y estado `activo`.
- **Movimiento (`Movimiento`):** evento inmutable de `entrada` o `salida` de un vehículo en un parqueadero, sin modelar cajones individuales internos.
- **Ocupación calculada (`ocupados`):** diferencia exacta entre entradas y salidas ($\text{entradas} - \text{salidas}$) de un parqueadero. Nunca se guarda en una columna mutable.
- **Disponibilidad (`disponibles`):** $\text{capacidad} - \text{ocupados}$.
- **Operador / Administrador de Parqueadero (`rol = "admin"`):** dueño de parqueadero o personal de seguridad encargado de poblar y mantener al día las entradas, salidas y datos de su(s) parqueadero(s). Puede estar restringido a un único `parqueo_id` o tener alcance sobre varios.
- **Superadministrador de la Aplicación (`rol = "superadmin"`):** perfil jerárquicamente superior que controla toda la plataforma, gestiona ciudades, parqueaderos, cuentas de operadores y sensores IoT, y consulta las analíticas globales de flujo y tráfico vehicular.
- **Dispositivo / Sensor (`Dispositivo`):** barrera electrónica, espira magnética o cámara de acceso que reporta entradas y salidas mediante el endpoint `/api/dispositivos/movimientos` usando su cabecera `X-Clave-Dispositivo`.
- **Índice de Rotación (`indice_rotacion`):** relación $\text{entradas\_totales} / \text{capacidad}$, que mide cuántas veces se ha renovado la capacidad de un parqueadero.
- **Flujo Neto (`flujo_neto`):** $\text{entradas} - \text{salidas}$ dentro de una franja horaria determinada.

---

## 4. Guía rápida para retomar en futuras sesiones

1. **Leer primero:** este archivo (`00-indice-sdd.md`) y [`01-especificacion-funcional-y-roles.md`](./01-especificacion-funcional-y-roles.md).
2. **Verificar el estado del backend (49 pruebas):**
   ```powershell
   cd C:\Users\dxlva\Desktop\parqueos-cuenca\backend
   .\.venv\Scripts\python.exe -m pytest
   ```
3. **Levantar entorno de desarrollo:**
   - Backend (`http://127.0.0.1:8000`):
     ```powershell
     cd C:\Users\dxlva\Desktop\parqueos-cuenca\backend
     .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
     ```
   - Frontend (`http://localhost:5173`):
     ```powershell
     cd C:\Users\dxlva\Desktop\parqueos-cuenca\frontend
     npm run dev
     ```
4. **Cuentas semilla en desarrollo (`cargar_datos_ejemplo = True`):**
   - **Superadministrador de la App (`/superadmin`):** `superadmin` / `balzai2026`
   - **Operador general de parqueaderos (`/admin`):** `admin` / `parqueos2026`
   - **Operador exclusivo de Parque Calderón (`/admin`):** `guardia_calderon` / `parqueos2026`
   - **Clave de sensor IoT (`X-Clave-Dispositivo`):** `sensor-demo-cuenca`
