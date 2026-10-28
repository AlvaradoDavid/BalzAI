# 02 — Especificación de Arquitectura y Modelo de Datos

## 1. Arquitectura general del sistema

```mermaid
flowchart LR
    subgraph Clientes["Clientes"]
        U["Navegador Ciudadano<br/>(Mapa React + Leaflet)"]
        O["Panel Operador<br/>(/admin)"]
        S["Consola Superadmin<br/>(/superadmin)"]
        D["Sensores / Barreras IoT<br/>(HTTP Client)"]
    end

    subgraph Backend["Backend Python (FastAPI)"]
        R_PUB["Router Público<br/>/api/ciudades, /api/parqueos"]
        R_AUTH["Router Auth<br/>/api/auth/login, /perfil"]
        R_ADM["Router Operación<br/>/api/admin/*"]
        R_SUP["Router Superadmin<br/>/api/superadmin/*"]
        R_DIS["Router Dispositivos<br/>/api/dispositivos/movimientos"]
        SVC_OC["Servicio Ocupación<br/>(app/servicios/ocupacion.py)"]
        SVC_AN["Servicio Analíticas y Control<br/>(app/servicios/analiticas.py)"]
    end

    subgraph Datos["Persistencia Relacional"]
        DB[("SQLite (MVP)<br/>PostgreSQL (Producción)")]
    end

    U --> R_PUB
    O --> R_AUTH
    O --> R_ADM
    S --> R_AUTH
    S --> R_SUP
    S --> R_ADM
    D --> R_DIS

    R_PUB --> SVC_OC
    R_ADM --> SVC_OC
    R_DIS --> SVC_OC
    R_SUP --> SVC_AN
    SVC_OC --> DB
    SVC_AN --> DB
```

---

## 2. Diagrama Entidad-Relación (ERD)

Definido en [`backend/app/models.py`](../backend/app/models.py):

```mermaid
erDiagram
    CIUDADES ||--o{ PARQUEOS : "contiene"
    PARQUEOS ||--o{ MOVIMIENTOS : "registra"
    PARQUEOS ||--o{ DISPOSITIVOS : "tiene instalados"
    PARQUEOS ||--o{ ADMINISTRADORES : "asigna alcance (opcional)"
    ADMINISTRADORES ||--o{ MOVIMIENTOS : "registra manualmente"
    DISPOSITIVOS ||--o{ MOVIMIENTOS : "registra automáticamente"

    CIUDADES {
        int id PK
        string slug UK
        string nombre
        string provincia
        float latitud
        float longitud
        int zoom
    }

    PARQUEOS {
        int id PK
        int ciudad_id FK
        string nombre
        string direccion
        float latitud
        float longitud
        int capacidad "CHECK > 0"
        boolean activo
        datetime creado_en
    }

    MOVIMIENTOS {
        bigint id PK
        int parqueo_id FK
        string tipo "entrada | salida"
        string origen "manual | dispositivo"
        int administrador_id FK "nullable"
        int dispositivo_id FK "nullable"
        datetime creado_en "INDEX"
    }

    ADMINISTRADORES {
        int id PK
        string usuario UK
        string nombre "nullable"
        string clave_hash "PBKDF2-HMAC-SHA256"
        string rol "admin | superadmin"
        int parqueo_id FK "nullable (alcance operador)"
        boolean activo
        datetime creado_en
    }

    DISPOSITIVOS {
        int id PK
        string nombre
        int parqueo_id FK
        string clave_hash UK "SHA-256 (64 hex)"
        boolean activo
        datetime creado_en
    }
```

---

## 3. Cálculo de ocupación y escritura atómica

### 3.1. Subconsulta correlacionada (`ocupacion_de`)
En [`app/servicios/ocupacion.py`](../backend/app/servicios/ocupacion.py), la ocupación se define como:

$$\text{ocupados}(p) = \text{COALESCE}\!\left(\sum_{m \in \text{movimientos}(p)} \begin{cases} +1 & \text{si } m.\text{tipo} = \text{'entrada'} \\ -1 & \text{si } m.\text{tipo} = \text{'salida'} \end{cases},\ 0\right)$$

Gracias al índice compuesto `ix_movimientos_parqueo_tipo (parqueo_id, tipo)`, el motor de base de datos resuelve esta suma con un *Index-Only Scan* sin leer el resto de columnas de la tabla.

### 3.2. Prevención de condiciones de carrera
Para impedir que dos peticiones concurrentes sobrepasen la capacidad o dejen la ocupación en negativo:
1. Se ejecuta `SELECT ... FROM parqueos WHERE id = :id FOR UPDATE` (`_bloquear_parqueo`), que serializa las transacciones sobre un mismo parqueo en PostgreSQL.
2. El movimiento se inserta mediante un `INSERT INTO movimientos (...) SELECT ... WHERE <regla>` atómico:
   - Si `tipo == 'entrada'`, la condición `WHERE` exige `ocupacion_de(parqueo_id) < capacidad`.
   - Si `tipo == 'salida'`, la condición `WHERE` exige `ocupacion_de(parqueo_id) > 0`.
3. Si `resultado.rowcount != 1`, se hace `rollback()` y se lanza `Conflicto` (`HTTP 409`). En SQLite, donde `INSERT` adquiere el bloqueo de escritura antes de evaluar su `SELECT`, esto garantiza atomicidad estricta sin ventanas TOCTOU (*Time-Of-Check to Time-Of-Use*).

---

## 4. Diseño de seguridad

Implementado en [`backend/app/seguridad.py`](../backend/app/seguridad.py) y [`backend/app/dependencias.py`](../backend/app/dependencias.py):

1. **Contraseñas humanas (`administradores.clave_hash`):**
   - Algoritmo `PBKDF2-HMAC-SHA256` con sal aleatoria de 16 bytes y `600,000` iteraciones (recomendación OWASP), comparadas en tiempo constante con `hmac.compare_digest`.
   - Cuando el usuario enviado en `/api/auth/login` no existe, igual se ejecuta `verificar_clave` contra `hash_ficticio()` para impedir la enumeración de usuarios por tiempos de respuesta.
2. **Tokens de sesión JWT:**
   - Firmados con `HS256`, contienen `sub` (ID de la cuenta), `rol` (`admin` | `superadmin`), `iat` y `exp`.
   - En cada petición protegida (`requiere_admin` / `requiere_superadmin`), además de verificar la firma y expiración del JWT, se consulta la fila `Administrador` en la base de datos para que desactivar una cuenta o revocar su rol tenga efecto inmediato.
3. **Claves de sensores IoT (`dispositivos.clave_hash`):**
   - Generadas con `secrets.token_urlsafe(32)` (256 bits de entropía).
   - Se almacena únicamente su resumen `SHA-256` indexado (`UNIQUE`), y la clave en texto claro solo se devuelve en la respuesta de creación (`201 Created`).
4. **Guardias de producción (`Settings._proteger_produccion`):**
   - Si `ENTORNO=produccion`, la aplicación se niega a arrancar si `JWT_SECRETO` conserva el valor por defecto de desarrollo o si `CARGAR_DATOS_EJEMPLO=true`.
