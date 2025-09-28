
# Ally360 API

Ally360 es un ERP SaaS multi-tenant construido con FastAPI, PostgreSQL y MinIO para gestión empresarial escalable.

## Características principales

### 🏢 Multi-tenant
- Arquitectura multi-tenant completa con aislamiento por empresa
- Middleware de tenant automático con `X-Company-ID`
- Queries siempre filtradas por `tenant_id`
- Provisioning automático de esquemas por empresa

### 🔐 Autenticación completa
- **Registro con verificación de email**
- **Login multi-empresa** con selección de contexto
- **Tokens de contexto** con información de tenant
- **Sistema de invitaciones** para empresas
- **Restablecimiento de contraseñas**
- **Roles contextuales**: owner, admin, seller, accountant, viewer

### 📁 Gestión de archivos
- Almacenamiento con **MinIO** (S3-compatible)
- **Presigned URLs** para subidas/descargas seguras
- **Metadata en BD** con información de tenant
- **Tareas asíncronas** para procesamiento

### 📧 Sistema de correos
- **Templates de Jinja2** personalizables
- **Envío asíncrono** con Celery
- **Emails transaccionales**: verificación, invitaciones, reset
- Configuración SMTP flexible

### ⚡ Escalabilidad
- **Async SQLAlchemy** para alto rendimiento
- **Redis** para cache y rate limiting
- **Celery** para tareas en background
- **PgBouncer-ready** para pool de conexiones

## Flujo de autenticación

### 1. Registro de usuario
```http
POST /auth/register
{
  "email": "owner@company.com",
  "password": "password123",
  "profile": {
    "first_name": "Juan",
    "last_name": "Pérez",
    "phone_number": "+1234567890"
  }
}
```

### 2. Verificación de email
```http
POST /auth/verify-email
{
  "token": "verification-token-from-email"
}
```

### 3. Login inicial
```http
POST /auth/login
{
  "username": "owner@company.com",
  "password": "password123"
}
```
Respuesta incluye lista de empresas disponibles.

### 4. Selección de empresa
```http
POST /auth/select-company
{
  "company_id": "uuid-de-la-empresa"
}
```
Retorna token de contexto con `tenant_id`.

### 5. Uso con contexto
```http
GET /products/
Authorization: Bearer <context-token>
# O alternativamente:
X-Company-ID: uuid-de-la-empresa
```

## Sistema de invitaciones

### Invitar usuario (owner/admin)
```http
POST /auth/invite-user
Authorization: Bearer <context-token>
{
  "email": "nuevo@usuario.com",
  "role": "seller"
}
```

### Aceptar invitación
```http
POST /auth/accept-invitation
{
  "token": "invitation-token-from-email",
  "password": "newpassword123",
  "profile": {
    "first_name": "María",
    "last_name": "García"
  }
}
```

## Estructura del proyecto

```
app/
├── common/          # Mixins, middleware compartido
├── core/            # Configuración, Celery
├── database/        # Conexión DB, migraciones
├── modules/
│   ├── auth/        # Autenticación completa
│   ├── company/     # Gestión de empresas
│   ├── email/       # Sistema de correos
│   ├── files/       # Gestión de archivos
│   ├── products/    # Productos
│   └── ...
├── dependencies/    # Inyección de dependencias
└── main.py         # App principal
```

## Desarrollo rápido

### 1. Configuración inicial
```bash
git clone <repository>
cd ally360-api
cp .env.example .env
# Editar .env con tus configuraciones de email
```

### 2. Ejecutar con Docker
```bash
docker-compose up --build
```

### 3. Generar migración inicial
```bash
# Una vez que los containers estén corriendo
docker-compose exec app python migrate.py create "Initial migration"
docker-compose exec app python migrate.py upgrade
```

## Servicios incluidos

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs  
- **PostgreSQL**: puerto 5432
- **Redis**: puerto 6379
- **MinIO**: http://localhost:9000 (Console: http://localhost:9001)
- **Celery Worker**: procesamiento en background

## Templates de email

Los templates están en `app/modules/email/templates/`. Son placeholders básicos listos para reemplazar con tus diseños:

- `verification_email.html` - Verificación de cuenta
- `invitation_email.html` - Invitaciones a empresas  
- `password_reset_email.html` - Restablecimiento de contraseña

Variables disponibles en cada template documentadas en los archivos.

## Variables de entorno clave

```env
# Email (requerido para funcionalidad completa)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_USERNAME=tu-email@gmail.com
EMAIL_PASSWORD=tu-app-password
EMAIL_FROM=tu-email@gmail.com
FRONTEND_URL=http://localhost:3000

# JWT
APP_SECRET_STRING=cambia-esta-clave-en-produccion

# Base de datos y servicios (ya configurados para Docker)
POSTGRES_USER=ally_user
POSTGRES_PASSWORD=ally_pass
# ... resto de configuraciones
```

## Próximos pasos

1. **Configurar email SMTP** en `.env`
2. **Reemplazar templates** de email con tus diseños
3. **Ejecutar primera migración**
4. **Probar flujo completo** de registro → verificación → login → selección empresa

## API Endpoints principales

- `POST /auth/register` - Registro con empresa
- `POST /auth/login` - Login multi-empresa
- `POST /auth/select-company` - Contexto de empresa
- `POST /auth/invite-user` - Invitar usuarios
- `GET /products/` - Productos (requiere tenant)
- `POST /files/upload` - Subir archivos
- Y muchos más en `/docs`

## 📄 Licencia

Proyecto privado bajo desarrollo. Todos los derechos reservados © Ally360.
