# 04 — Especificación de Frontend, UX y Sistema Apple Design

## 1. Mapa de rutas y vistas

Definido en [`frontend/src/App.jsx`](../frontend/src/App.jsx):

| Ruta | Componente | Rol destinatario | Función principal |
| :--- | :--- | :--- | :--- |
| `/` | [`PaginaMapa.jsx`](../frontend/src/paginas/PaginaMapa.jsx) | Público (conductores) | Mapa interactivo Leaflet + OpenStreetMap, marcadores con espacios libres y tarjeta flotante de detalle. |
| `/admin` | [`PaginaAdmin.jsx`](../frontend/src/paginas/PaginaAdmin.jsx) | Operadores / Dueños (`admin`) y `superadmin` | Registro rápido de `+ Entrada` y `− Salida`, creación y edición de parqueaderos dentro de su alcance. |
| `/superadmin` | [`PaginaSuperAdmin.jsx`](../frontend/src/paginas/PaginaSuperAdmin.jsx) | Superadministrador (`superadmin`) | Consola de control global: Analíticas, Flujo y Tráfico por hora, Gestión de Operadores/Dueños y Gestión de Ciudades y Sensores IoT. |

---

## 2. Principios de Apple Design implementados

El frontend aplica las directrices de la skill `apple-design` (*WWDC Designing Fluid Interfaces* y *The Details of UI Typography*):

### 2.1. Latencia cero en la respuesta (`§1 Response`)
- **Selección optimista en el mapa:** al pulsar un marcador en `PaginaMapa.jsx`, el panel pinta de inmediato (0 ms) el parqueo ya disponible en memoria mientras revalida en segundo plano con `GET /api/parqueos/{id}`.
- **Feedback en `pointer-down`:** todos los botones, segmentos, enlaces y marcadores responden en `:active` (`transform: scale(0.96); transition: transform 100ms ease-out;`), sin esperar al evento `click`.

### 2.2. Manipulación directa 1:1, interrumpibilidad y resortes (`src/fisica.js`)
El módulo [`frontend/src/fisica.js`](../frontend/src/fisica.js) implementa:
- **`crearResorte({ valorInicial, damping, response, onCambio, onReposo })`:**
  - Parametrizado por `damping` (amortiguación: `1.0` críticamente amortiguado por defecto; `0.82` con ligero rebote cuando proviene de un gesto con impulso) y `response` (rapidez en segundos, `0.30`–`0.38` s), con frecuencia natural $\omega_n = 2\pi / \text{response}$.
  - Siempre anima desde el valor de presentación actual y conserva la velocidad cuando se redirige (`irA`) o se agarra a mitad de vuelo (`fijar`).
- **`proyectar(velocidadInicial, tasaDesaceleracion = 0.998)`:**
  - Calcula dónde descansaría el gesto por desaceleración exponencial:
    $$\Delta x = \frac{v_0}{1000} \cdot \frac{d}{1 - d}$$
- **`ligaElastica(exceso, dimension, constante = 0.55)`:**
  - Resistencia progresiva (*rubber-banding*) cuando el usuario arrastra `PanelParqueo.jsx` más allá de su posición abierta.
- **`RastreadorVelocidad`:**
  - Muestrea los últimos `~100 ms` de eventos `pointermove` para entregar la velocidad real en `px/s` al resorte en el instante de `pointerup`.

### 2.3. Materiales translúcidos y jerarquía espacial (`§12 Materials & depth`)
- En [`frontend/src/estilos.css`](../frontend/src/estilos.css), la cabecera, la píldora de resumen de ciudad y el panel de parqueadero usan `.cristal` (`backdrop-filter: blur(22px) saturate(180%)` + borde especular `rgba(255, 255, 255, 0.65)`) flotando sobre el mapa a pantalla completa.
- Consistencia espacial (`§7`): en escritorio el panel entra y sale horizontalmente desde la derecha; en móvil (`<= 760px`) se transforma en un *bottom sheet* con tirador superior que emerge y se descarta verticalmente hacia abajo.

### 2.4. Tipografía óptica y números tabulares (`§15 Typography`)
- Fuente del sistema con `font-optical-sizing: auto`.
- *Tracking* negativo y *leading* cerrado en cifras grandes (`.cifra strong`, `.kpi-valor`: `letter-spacing: -0.03em; line-height: 1.05`), *tracking* positivo en etiquetas e insignias (`.etiqueta`, `.insignia-rol`: `letter-spacing: 0.02em`).
- `font-variant-numeric: tabular-nums` en marcadores, contadores, tablas y gráficos para evitar saltos horizontales al actualizarse las cifras.

### 2.5. Accesibilidad y preferencias del usuario (`§14 Reduced motion`)
- `@media (prefers-reduced-motion: reduce)`: tanto CSS como `movimientoReducido()` en `fisica.js` desactivan resortes y desplazamientos elásticos, resolviendo los cambios de estado sin movimiento vestibular.
- `@media (prefers-reduced-transparency: reduce)`: reemplaza `backdrop-filter` por superficies opacas de alto contraste.
- `@media (prefers-contrast: more)`: refuerza bordes de `2px solid #111827`.
