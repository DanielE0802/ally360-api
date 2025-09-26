# Ally360 – INSTRUCTION.md

Este documento define cómo debe trabajar GitHub Copilot dentro del proyecto **Ally360 (ERP SaaS en FastAPI)**.  
Su objetivo es asegurar que el código generado siga las guías arquitectónicas, técnicas y de escalabilidad necesarias para un SaaS multi-tenant robusto.

---

## 📊 Contexto del Proyecto
- **Nombre:** Ally360
- **Tipo:** ERP SaaS multi-tenant
- **Backend:** FastAPI (Python 3.11+)
- **Base de Datos:** PostgreSQL + SQLAlchemy ORM
- **Autenticación:** JWT (con refresh tokens)
- **Archivos:** MinIO (S3 compatible)
- **Infraestructura:** Docker + Docker Compose (Kubernetes en producción futura)
- **Cache/Jobs:** Redis + Celery (para tareas asincrónicas y rate limiting)
- **Objetivo:** MVP funcional, escalable y listo para multi-empresa.

---

## 🏗️ Reglas Generales de Desarrollo
1. **Multi-tenancy obligatorio**
   - Cada tabla de negocio debe incluir `tenant_id`.
   - Las queries deben filtrar siempre por `tenant_id`.
   - Endpoints deben validar que el `user` pertenece al `tenant_id` del request.
   - Middleware debe resolver `tenant_id` desde `X-Company-ID` o selección de empresa.

2. **Arquitectura por capas**
   - `router.py` → solo define endpoints.
   - `service.py` → lógica de negocio.
   - `crud.py` → acceso a BD.
   - `models.py` → SQLAlchemy models.
   - `schemas.py` → validaciones Pydantic.
   - `dependencies.py` → inyección de dependencias.

3. **Base de datos**
   - IDs siempre `UUID`.
   - `created_at`, `updated_at`, `deleted_at` en tablas principales.
   - Uso de Alembic para migraciones.
   - PgBouncer para pool de conexiones.
   - Índices compuestos con `tenant_id`.

4. **Archivos (MinIO)**
   - Un único bucket `ally360`.
   - Prefijos: `ally360/{tenant_id}/{module}/{yyyy}/{mm}/{dd}/{uuid}`.
   - Subidas y descargas solo por **presigned URLs**.
   - Tabla `files` en BD con metadata (`tenant_id`, `key`, `size`, `content_type`, `uploaded_by`).

5. **Autenticación y autorización**
   - JWT con expiración corta + refresh tokens.
   - Roles contextuales por `(user_id, tenant_id)`.
   - Roles base: `owner`, `admin`, `seller`, `accountant`.

6. **Escalabilidad**
   - Redis para cache de roles y rate limiting por tenant.
   - Celery + Redis para reportes, antivirus, thumbnails, tareas pesadas.
   - Endpoints grandes deben usar **paginación keyset**.
   - Configurar GZip en respuestas.

7. **Seguridad**
   - Validación estricta en Pydantic.
   - Rate limiting por tenant.
   - Tamaño máximo de request.
   - Auditoría en tabla `audit_logs`.

8. **Testing**
   - Unit tests para modelos y servicios.
   - Integration tests multi-tenant (asegurando que un tenant no ve datos de otro).
   - Contract tests contra OpenAPI.

---

## 🚀 Buenas Prácticas para Copilot
- **Siempre incluir `tenant_id` en modelos y queries**.
- **Generar migrations de Alembic** cuando se modifiquen modelos.
- **No exponer archivos directamente desde MinIO** → usar presigned URLs.
- **Validar límites de plan (`tenant_limits`)** en endpoints críticos.
- **Seguir patrones de código existentes** (router → service → crud).
- **Usar async SQLAlchemy sessions** donde sea posible.
- **Escribir pruebas junto con nuevas features**.

---

## 📂 Estructura Recomendada
ally360/
│── core/ # Configuración
│── database/ # Conexión, migraciones
│── auth/ # Usuarios, roles, JWT
│── company/ # Empresas, planes
│── products/ # Productos, variantes
│── inventory/ # Stocks, movimientos
│── files/ # Manejo MinIO
│── common/ # Utils, middlewares
│── tests/ # Tests unitarios e integración


---

## ✅ Ejemplos Rápidos

**Modelo con tenant_id**
```python
class Product(Base, TenantMixin):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String, nullable=False)
    sku = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "sku"),)

Middleware de tenant

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Company-ID")
        request.state.tenant_id = tenant_id
        return await call_next(request)

Presigned URL MinIO

def presign_upload(tenant_id: str, module: str, filename: str):
    key = f"{tenant_id}/{module}/{uuid4()}/{filename}"
    url = minio_client.presigned_put_object("ally360", key, expires=timedelta(minutes=15))
    return {"key": key, "url": url}


Este documento debe ser seguido siempre que Copilot o un desarrollador humano genere código en este repositorio.

You are coding in the Ally360 SaaS ERP project built with FastAPI, PostgreSQL (SQLAlchemy), and MinIO.

Always:
- Add `tenant_id` to every business table and filter queries by `tenant_id`.
- Use UUIDs as primary keys.
- Generate Alembic migrations when changing models.
- Separate concerns: router → service → crud → models → schemas.
- For file handling, only use MinIO with presigned URLs. Store metadata in a `files` table with `tenant_id`.
- Ensure scalability: async SQLAlchemy sessions, Redis cache, Celery jobs, PgBouncer-ready connections.
- Ensure security: validate tenant ownership, rate limit requests, restrict file types and sizes.
- Always include tests for new features.
- Write code consistent with existing patterns.

Focus right now on:  
1. TenantMiddleware (`X-Company-ID` → `request.state.tenant_id`).  
2. TenantMixin for SQLAlchemy models (`tenant_id` + scoped unique constraints).  
3. MinIO presigned upload/download endpoints.  
4. Enforce queries always scoped by `tenant_id`.  
5. Use pagination (limit/offset or keyset) for large lists.  

Do not generate code that leaks data between tenants.  
