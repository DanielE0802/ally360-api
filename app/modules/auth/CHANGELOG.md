# 📋 CHANGELOG - Auth Module

Historial de cambios y evolución del módulo de autenticación de **Ally360 ERP SaaS**.

## 🚀 [1.0.0] - 2024-12-19 - **MVP COMPLETO**

### ✨ **FEATURES PRINCIPALES**

#### 🔐 **Sistema de Autenticación Multi-Tenant**
- **JWT doble token**: Access token + Context token para empresas
- **Multi-company support**: Un usuario puede pertenecer a múltiples empresas
- **Role-based access control (RBAC)**: 5 roles jerárquicos (owner → viewer)
- **Tenant isolation**: Aislamiento completo de datos por empresa

#### 👤 **Gestión de Usuarios**
- **Registro completo**: User + Profile en transacción
- **Verificación de email**: Tokens seguros con expiración 24h
- **Activación de cuenta**: Solo usuarios verificados pueden hacer login
- **Soft delete**: Implementado con TimestampMixin

#### 🔑 **Seguridad Avanzada**
- **Contraseñas seguras**: Hash bcrypt con 12 rounds
- **Tokens criptográficos**: Generación con `secrets` module
- **JWT seguro**: HS256, expiración corta, refresh rotation
- **Rate limiting**: Protección contra ataques de fuerza bruta

#### 📧 **Sistema de Emails**
- **Verificación de cuenta**: Email automático post-registro
- **Reset de contraseña**: Tokens temporales de 1 hora
- **Invitaciones**: Sistema completo de invitaciones por empresa
- **Templates responsivos**: HTML y texto plano
- **Celery integration**: Envío asíncrono de emails

#### 👥 **Sistema de Invitaciones**
- **Flujo completo**: Invitar → Email → Aceptar → Registro automático
- **Validación de permisos**: Solo owners/admins pueden invitar
- **Tokens únicos**: 7 días de expiración, no reutilizables
- **Gestión de estado**: Pendiente → Aceptada → Expirada

### 🏗️ **ARQUITECTURA IMPLEMENTADA**

#### **Modelos de Datos**
```sql
-- Tabla principal de usuarios
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT false,
    email_verified BOOLEAN DEFAULT false,
    email_verified_at TIMESTAMPTZ,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Perfiles de usuario (información personal)
CREATE TABLE profiles (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    phone VARCHAR,
    avatar_url VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Relación usuario-empresa con roles
CREATE TABLE user_companies (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    company_id UUID NOT NULL, -- tenant_id
    role user_role_enum NOT NULL,
    is_active BOOLEAN DEFAULT true,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, company_id)
);
```

#### **Capas de Servicio**
- **Router Layer**: Endpoints REST con validación OpenAPI
- **Service Layer**: Lógica de negocio y orquestación
- **CRUD Layer**: Operaciones de base de datos
- **Dependencies Layer**: Inyección de dependencias y validaciones
- **Tasks Layer**: Background jobs con Celery

#### **Sistema de Tokens**
```python
# Access Token (sin empresa específica)
{
  "sub": "user-uuid",
  "type": "access",
  "exp": 1735123456
}

# Context Token (con empresa y rol)
{
  "sub": "user-uuid", 
  "tenant_id": "company-uuid",
  "role": "admin",
  "type": "context",
  "exp": 1735123456
}
```

### 🌐 **ENDPOINTS IMPLEMENTADOS**

#### **Autenticación Principal**
- `POST /auth/register` - Registro de nuevo usuario
- `POST /auth/login` - Login con email/password
- `POST /auth/select-company` - Seleccionar empresa (context token)
- `POST /auth/refresh` - Renovar tokens
- `POST /auth/logout` - Cerrar sesión

#### **Verificación y Recuperación**
- `GET /auth/verify-email/{token}` - Verificar email
- `POST /auth/resend-verification` - Reenviar verificación
- `POST /auth/forgot-password` - Solicitar reset
- `POST /auth/reset-password` - Cambiar contraseña

#### **Invitaciones**
- `POST /auth/invite-user` - Invitar usuario (admin/owner)
- `GET /auth/invitations` - Listar invitaciones enviadas
- `POST /auth/accept-invitation` - Aceptar invitación
- `DELETE /auth/invitations/{id}` - Cancelar invitación

#### **Perfil y Gestión**
- `GET /auth/me` - Información del usuario actual
- `PUT /auth/me` - Actualizar perfil
- `GET /auth/companies` - Listar mis empresas
- `PUT /auth/change-password` - Cambiar contraseña

### 🛡️ **SISTEMA DE ROLES**

#### **Jerarquía Implementada**
1. **OWNER** - Propietario de la empresa (todos los permisos)
2. **ADMIN** - Administrador (gestión completa excepto eliminar empresa)
3. **SELLER** - Vendedor (ventas, clientes, productos)
4. **ACCOUNTANT** - Contador (facturas, reportes, contabilidad)
5. **VIEWER** - Solo lectura (consultas únicamente)

#### **Matriz de Permisos**
| Funcionalidad | Owner | Admin | Seller | Accountant | Viewer |
|---------------|-------|-------|---------|------------|--------|
| Invitar usuarios | ✅ | ✅ | ❌ | ❌ | ❌ |
| Gestionar empresa | ✅ | ✅ | ❌ | ❌ | ❌ |
| Crear/editar productos | ✅ | ✅ | ✅ | ❌ | ❌ |
| Ver facturas | ✅ | ✅ | ✅ | ✅ | ✅ |
| Crear facturas | ✅ | ✅ | ✅ | ❌ | ❌ |
| Ver reportes | ✅ | ✅ | ❌ | ✅ | ✅ |
| Configuraciones | ✅ | ✅ | ❌ | ❌ | ❌ |

### 🔧 **DEPENDENCIES IMPLEMENTADAS**

#### **AuthContext System**
```python
@dataclass
class AuthContext:
    user: User              # Usuario autenticado
    tenant_id: UUID         # Empresa seleccionada
    role: UserRole         # Rol en la empresa
    permissions: List[str]  # Permisos calculados
```

#### **Role Validation**
```python
# Validar roles específicos
require_role([UserRole.OWNER, UserRole.ADMIN])

# Validar permisos granulares (futuro)
require_permission(["users.invite", "company.manage"])

# Validar tenant ownership automático
get_current_tenant()  # Siempre valida que user pertenece al tenant
```

### 📧 **SISTEMA DE EMAILS IMPLEMENTADO**

#### **Templates Creados**
- **Verificación de cuenta**: Bienvenida + enlace verificación
- **Reset de contraseña**: Enlace seguro temporal
- **Invitación a empresa**: Información + enlace aceptación
- **Confirmación de acciones**: Registro exitoso, cambio contraseña

#### **Configuración SMTP**
- **Proveedor**: Configurable (Gmail, SendGrid, AWS SES)
- **Templates**: HTML responsivo + fallback texto plano
- **Tracking**: Tokens únicos para seguimiento
- **Rate limiting**: Control de envío por usuario/IP

### 🎯 **VALIDACIONES IMPLEMENTADAS**

#### **Pydantic Schemas (v2)**
```python
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        # Validar complejidad de contraseña
        return v
```

#### **Validaciones de Negocio**
- **Email único**: No duplicados en sistema
- **Contraseña segura**: Mínimo 8 caracteres, complejidad
- **Roles válidos**: Solo roles definidos en enum
- **Tenant ownership**: Usuario debe pertenecer a la empresa
- **Token validity**: Expiración, un solo uso, estado correcto

### 🔄 **BACKGROUND TASKS**

#### **Celery Tasks Implementadas**
```python
# Envío de emails
@celery_app.task
def send_verification_email_task(user_email, user_name, token, company_name):
    """Enviar email de verificación de cuenta"""

@celery_app.task  
def send_password_reset_task(user_email, user_name, reset_token):
    """Enviar email de reset de contraseña"""

@celery_app.task
def send_invitation_email_task(invite_email, company_name, inviter_name, token):
    """Enviar email de invitación a empresa"""

# Limpieza automática
@celery_app.task
def cleanup_expired_tokens_task():
    """Limpiar tokens expirados cada 24h"""
```

### 📊 **MÉTRICAS Y MONITORING**

#### **Logs Implementados**
- **Login attempts**: Exitosos y fallidos
- **Email verifications**: Enviados y confirmados  
- **Password resets**: Solicitados y completados
- **Invitations**: Enviadas, aceptadas, expiradas
- **Role changes**: Cambios de rol por empresa
- **Security events**: Intentos de acceso no autorizado

#### **Health Checks**
- **Database connectivity**: Users, tokens tables
- **Email service**: SMTP connection
- **Celery workers**: Background tasks status
- **JWT validation**: Token generation/verification

---

## 🔄 **VERSIONES ANTERIORES**

### [0.9.0] - 2024-12-15 - **Pre-MVP**
- Implementación inicial de JWT
- Modelos básicos User/Profile
- Endpoints básicos de auth
- Sistema de roles simple

### [0.8.0] - 2024-12-10 - **Alpha**
- Estructura inicial del módulo
- Configuración base de dependencias
- Integración con SQLAlchemy
- Tests básicos

---

## 🎯 **ROADMAP FUTURO**

### [1.1.0] - **Q1 2025** - Mejoras de Seguridad
- [ ] **Two-Factor Authentication (2FA)**
  - SMS + Email + Authenticator apps
  - Backup codes de emergencia
  - Configuración por usuario
  
- [ ] **OAuth2 Social Login**
  - Google, Microsoft, GitHub
  - Account linking automático
  - Profile sync

- [ ] **Advanced Session Management**
  - Device tracking y confianza
  - Logout remoto de dispositivos
  - Detección de ubicaciones sospechosas

### [1.2.0] - **Q2 2025** - API & Integraciones
- [ ] **API Keys Management**
  - Keys para integraciones externas
  - Scopes y rate limiting por key
  - Audit trail de API usage

- [ ] **Webhook System**
  - Events de auth (login, logout, role change)
  - Retry logic y failure handling
  - Signature validation

### [1.3.0] - **Q3 2025** - Escalabilidad
- [ ] **Advanced Rate Limiting**
  - Por tenant, usuario, endpoint
  - Sliding window algorithm
  - Redis-based distributed limiting

- [ ] **Microservice Ready**
  - Auth como servicio independiente
  - gRPC + REST interfaces
  - Service mesh integration

### [1.4.0] - **Q4 2025** - Compliance & Analytics
- [ ] **GDPR Compliance**
  - Data export/deletion
  - Consent management
  - Privacy controls

- [ ] **Analytics Dashboard**
  - Login patterns por tenant
  - Security metrics
  - User behavior insights

---

## ⚠️ **BREAKING CHANGES**

### **v1.0.0**
- **Pydantic v2**: Migración completa de validators
- **JWT Structure**: Cambio de estructura de tokens (access + context)
- **Role System**: Nuevos roles y jerarquía
- **Database Schema**: Nuevas tablas y relaciones

### **Migración desde v0.9.x**
```bash
# 1. Actualizar dependencias
pip install pydantic==2.5.0 fastapi==0.104.0

# 2. Ejecutar migraciones
alembic upgrade head

# 3. Regenerar tokens existentes (invalidar sesiones)
python scripts/invalidate_old_tokens.py

# 4. Actualizar clientes para usar nuevo flujo de login
```

---

## 🐛 **KNOWN ISSUES**

### **v1.0.0**
- **Email Templates**: Algunos clientes de email pueden no renderizar CSS correctamente
- **Token Refresh**: Race condition posible en refresh concurrente (mitigado con locks)
- **Celery Tasks**: Retry logic básico, necesita mejoras para alta disponibilidad

### **Workarounds**
```python
# Email template fallback
if not html_support:
    use_plain_text_template()

# Token refresh con lock
with redis_lock(f"refresh:{user_id}"):
    new_tokens = refresh_user_tokens(refresh_token)
```

---

## 🏆 **CONTRIBUTORS**

- **Auth Module Lead**: Sistema completo de autenticación
- **Security Review**: Validación de seguridad y best practices  
- **Testing**: Suite completa de tests unitarios e integración
- **Documentation**: README técnico y ejemplos de uso

---

## 📞 **SUPPORT**

Para issues relacionados con el módulo de autenticación:

1. **Bugs**: Crear issue en GitHub con label `auth`
2. **Security Issues**: Enviar email privado al team de seguridad
3. **Features**: Discutir en GitHub Discussions
4. **Documentation**: PRs bienvenidos para mejoras

---

**Changelog actualizado:** 19 Diciembre 2024  
**Próxima release:** v1.1.0 (Q1 2025)  
**Versión actual:** 1.0.0 (Stable)