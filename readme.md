
# Ally360 API

Ally360 es un ERP SaaS multi-tenant construido con FastAPI, PostgreSQL y MinIO. Este repositorio contiene la API backend con arquitectura por capas, autenticación basada en JWT y manejo de archivos por presigned URLs. Está orientado a escalabilidad, seguridad y aislamiento por empresa (tenant).

## Contenidos

- Visión general
- Arquitectura y tecnologías
- Multi-tenancy y seguridad
- Módulos principales
- Estructura del repositorio
- Puesta en marcha (Docker)
- Migraciones de base de datos (Alembic)
- Variables de entorno
- Flujo de autenticación
- Manejo de archivos (MinIO)
- Tareas y cache (Celery/Redis)
- Guía de desarrollo y estándares
- Testing y verificación
- Solución de problemas frecuentes

## Visión general

Objetivo: ofrecer un ERP SaaS multi-empresa listo para crecer. Cada empresa es un tenant, todas las consultas se aíslan por `tenant_id`, y los flujos críticos contemplan seguridad y rendimiento.

Características clave
- Multi-tenant con aislamiento estricto por `tenant_id`.
- Autenticación JWT con selección de empresa y roles contextuales.
- Manejo de archivos en MinIO con URLs prefirmadas (subida y descarga).
- Arquitectura por capas: router → service → crud → models → schemas.
- Async SQLAlchemy donde aplica, Redis para cache y rate limiting, Celery para trabajos en background.
- Preparado para PgBouncer y despliegues escalables.

## Arquitectura y tecnologías

- FastAPI (Python 3.11+)
- PostgreSQL + SQLAlchemy ORM 2.x
- Alembic para migraciones
- MinIO (S3-compatible)
- Redis (cache, rate limiting)
- Celery (tareas asíncronas)
- Docker y Docker Compose

Principios de diseño
- Multi-tenancy obligatorio: todas las tablas de negocio incluyen `tenant_id` y todas las queries lo filtran.
- Capas separadas y responsabilidades claras.
- Seguridad por defecto: validaciones fuertes en Pydantic, rate limiting por tenant, JWT con expiración corta.
- Escalabilidad: uso de Redis, Celery, y conexiones listas para PgBouncer.

## Multi-tenancy y seguridad

Resolución de tenant
- Middleware extrae el `tenant_id` del header `X-Company-ID` y lo coloca en `request.state.tenant_id`.
- Alternativamente, se puede usar un token de contexto con `tenant_id` empaquetado.

Modelos con tenant
- Todas las entidades de negocio heredan o incluyen `tenant_id`. Índices compuestos suelen incluir `tenant_id` para rendimiento.

Autenticación y autorización
- JWT con tipo de token `access` y `context`.
- Roles por empresa: `owner`, `admin`, `seller`, `accountant`, `viewer`.
- Dependencias de auth validan que el usuario pertenece al tenant antes de acceder a rutas.

## Módulos principales

- auth: autenticación, usuarios, perfiles, invitaciones, roles contextuales, selección de empresa.
- contacts: contactos unificados (clientes y proveedores), validaciones fiscales básicas (CC, NIT con DV), direcciones flexibles.
- products: catálogo de productos, variantes, stocks por PDV, imágenes con MinIO.
- invoices: facturas de venta y POS, pagos asociados, secuencias por PDV.
- bills: compras y pagos a proveedores.
- files: integración con MinIO, generación de presigned URLs.
- pos/pdv: modelos y endpoints de punto de venta y vendedores.
- common/core/database/dependencies: utilidades, configuración, Celery, conexión DB, inyección de dependencias.

## Estructura del repositorio

```
app/
  common/
  core/
  database/
  dependencies/
  modules/
    auth/
    contacts/
    products/
    invoices/
    bills/
    files/
    pos/
    inventory/
    ...
  main.py
alembic/
  env.py
  versions/
docker/
docker-compose.yml
migrate.py
requirements.txt
```

## Puesta en marcha (Docker)

Requisitos
- Docker y Docker Compose instalados.

Pasos
```
git clone <repository>
cd ally360-api
cp .env.example .env   # Ajusta credenciales y secretos
docker compose up --build
```

Servicios expuestos
- API: http://localhost:8000
- Documentación OpenAPI: http://localhost:8000/docs
- PostgreSQL: puerto 5432 (contenedor postgres)
- Redis: puerto 6379
- MinIO API: http://localhost:9000
- MinIO Console: http://localhost:9001

## Migraciones de base de datos (Alembic)

Este proyecto incluye un helper `migrate.py`.

Aplicar migraciones pendientes
```
docker compose exec api python migrate.py upgrade
```

Crear una nueva migración (autogenerada)
```
docker compose exec api python migrate.py create "<mensaje>"
```

Revertir la última migración
```
docker compose exec api python migrate.py downgrade
```

Nota: Las migraciones deben revisarse antes de aplicar en producción.

## Variables de entorno

Base de datos y servicios
```
POSTGRES_USER=ally_user
POSTGRES_PASSWORD=ally_pass
POSTGRES_DB=ally_db
POSTGRES_HOST=postgres
REDIS_HOST=redis
```

JWT y seguridad
```
APP_SECRET_STRING=cambia-esta-clave-en-produccion
ALGORITHM=HS256
```

MinIO
```
MINIO_HOST=minio
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_PUBLIC_HOST=localhost
MINIO_PUBLIC_PORT=9000
```

Email (opcional, para flujos de verificación e invitación)
```
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_USERNAME=tu-email@gmail.com
EMAIL_PASSWORD=tu-app-password
EMAIL_FROM=tu-email@gmail.com
FRONTEND_URL=http://localhost:3000
```

## Flujo de autenticación

Registro y verificación
```
POST /auth/register
POST /auth/verify-email
```

Login y selección de empresa
```
POST /auth/login
POST /auth/select-company    # devuelve token de contexto con tenant
```

Uso con contexto
```
Authorization: Bearer <context-token>
X-Company-ID: <uuid-empresa>   # alternativa para selección de tenant
```

## Manejo de archivos (MinIO)

- Bucket único por entorno (por ejemplo, ally360).
- Claves con prefijos: `ally360/{tenant_id}/{module}/{yyyy}/{mm}/{dd}/{uuid}`.
- Todas las subidas/descargas se hacen por presigned URLs; nunca se expone el archivo directamente.
- Se guardan metadatos en base de datos (tabla files o equivalente por feature).
- El backend genera URLs prefirmadas usando el host público configurado (`MINIO_PUBLIC_HOST` y `MINIO_PUBLIC_PORT`).

## Tareas y cache (Celery/Redis)

- Celery para trabajos en background: emails, procesamiento de archivos, reportes.
- Redis como broker y caché para roles y rate limiting por tenant.

## Guía de desarrollo y estándares

- Multi-tenant obligatorio: siempre incluir y filtrar por `tenant_id`.
- Arquitectura por capas: router → service → crud → models → schemas.
- Pydantic v2 para validación estricta de entrada y salida.
- Consultas grandes con paginación (limit/offset o keyset).
- Configurar GZip y tiempos de expiración de JWT adecuados.
- Generar una migración de Alembic por cada cambio en modelos.

## Testing y verificación

- Pruebas unitarias para modelos y servicios.
- Pruebas de integración multi-tenant (un tenant no debe ver los datos de otro).
- Contract tests contra OpenAPI cuando aplique.

Quality gates recomendados
- Linter y type-check (pylance/mypy opcional).
- Construcción sin errores.
- Migraciones aplican sin conflictos.

## Solución de problemas frecuentes

Presigned URLs inaccesibles o con error de firma
- Asegúrate de configurar `MINIO_PUBLIC_HOST=localhost` y `MINIO_PUBLIC_PORT=9000` para desarrollo.
- Las URLs deben ser generadas usando el host público, no el nombre interno del contenedor.

Error ARRAY.contains() no implementado
- Usa `sqlalchemy.dialects.postgresql.ARRAY` en modelos para columnas array.

Columna faltante después de agregar un campo en modelos
- Crea y aplica una migración Alembic para reflejar el cambio en DB.

Errores de autorización por empresa
- Verifica que se envía `X-Company-ID` válido o que el token de contexto contiene `tenant_id`.

## Licencia

Proyecto privado en desarrollo. Todos los derechos reservados © Ally360.
