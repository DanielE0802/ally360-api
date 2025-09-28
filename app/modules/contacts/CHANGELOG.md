# Changelog - Módulo de Contactos

Todas las modificaciones importantes del módulo de contactos serán documentadas en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added - Funcionalidades Nuevas
- ✨ **Sistema unificado de contactos** que reemplaza Customer y Supplier
- 🏢 **Arquitectura multi-tenant** con aislamiento por `company_id`
- 🇨🇴 **Validaciones fiscales colombianas**:
  - Cálculo automático de dígito verificador NIT
  - Función `calculate_nit_dv()` para NITs colombianos
  - Función `validate_nit_with_dv()` para validación completa
  - Soporte tipos de documento: CC, NIT, CE, Pasaporte
  - Responsabilidades fiscales configurables
- 🔄 **Tipos flexibles de contacto**:
  - Cliente (`client`) para facturación
  - Proveedor (`provider`) para compras
  - Mixto (cliente Y proveedor simultáneamente)
- 🗑️ **Soft delete con auditabilidad**:
  - Campo `deleted_at` para eliminación lógica
  - Métodos `soft_delete()` y `restore()`
  - Mantiene integridad referencial
- 📎 **Sistema de adjuntos**:
  - Documentos como RUT, cédula, certificados
  - Integración con MinIO para almacenamiento
  - Metadata completa: tamaño, tipo MIME, descripción
- 🔍 **Búsqueda avanzada**:
  - Filtros por tipo, estado, vendedor
  - Búsqueda de texto libre (nombre, email, documento)
  - Paginación con límites configurables
- 📊 **Estadísticas y reportes**:
  - Conteos por tipo de contacto
  - Estadísticas de activos/inactivos/eliminados
  - Métricas de uso por empresa

### API Endpoints
- `POST /contacts/` - Crear contacto
- `GET /contacts/` - Listar con filtros y paginación
- `GET /contacts/{id}` - Obtener contacto específico
- `PUT /contacts/{id}` - Actualizar contacto
- `DELETE /contacts/{id}` - Eliminación suave (soft delete)
- `POST /contacts/{id}/restore` - Restaurar contacto eliminado
- `GET /contacts/stats/summary` - Estadísticas generales
- `GET /contacts/clients/for-invoices` - Clientes para facturas
- `GET /contacts/providers/for-bills` - Proveedores para compras
- `POST /contacts/{id}/attachments` - Subir documento adjunto
- `DELETE /contacts/attachments/{id}` - Eliminar adjunto
- `POST /contacts/bulk/activate` - Activar múltiples contactos
- `POST /contacts/bulk/deactivate` - Desactivar múltiples contactos

### Database Schema
- **Tabla `contacts`**: Entidad principal con todos los campos necesarios
- **Tabla `contact_attachments`**: Adjuntos de documentos
- **Índices optimizados**: Para multi-tenancy y búsquedas frecuentes
- **Constraints únicos**: `(company_id, id_number)` para evitar duplicados

### Models y Schemas
- `Contact` model con validaciones colombianas
- `ContactAttachment` model para adjuntos
- Enums: `ContactType`, `IdType`, `PersonType`
- Schemas Pydantic completos para validación
- Métodos helper: `is_client()`, `is_provider()`

### Services
- `ContactService`: Lógica de negocio principal
- `ContactAttachmentService`: Gestión de adjuntos
- Validaciones de negocio y manejo de errores
- Integración con otros módulos

### Security & Validation
- Validación estricta de pertenencia por tenant
- Sanitización de inputs
- Validación de documentos colombianos
- Restricciones de acceso por empresa

### Testing
- Tests unitarios para modelos
- Tests de integración para API
- Tests de validación NIT colombiano
- Tests de multi-tenancy isolation

### Documentation
- 📚 README.md completo con ejemplos
- 📝 Documentación de API en endpoints
- 🔧 Guías de integración con otros módulos
- 📊 Diagramas de arquitectura y flujos

---

## [Unreleased] - Próximas Funcionalidades

### Planned - En Planificación
- 🚀 **Cache Redis** para mejora de performance
- 📤 **Exportación masiva** (Excel, CSV)
- 🔔 **Webhooks** para notificaciones de cambios
- 🌐 **API GraphQL** como alternativa a REST
- 📈 **Analytics avanzado** de contactos
- 🔗 **Integración CRM externo** (HubSpot, Salesforce)

### Consider - Bajo Consideración
- 📱 **App móvil** para gestión de contactos
- 🤖 **IA para duplicados** automática
- 🔄 **Sincronización multi-empresa**
- 🛒 **Marketplace de contactos**
- 📊 **Scoring automático** de clientes

---

## Guía de Versionado

### Major (X.0.0)
- Cambios incompatibles en API
- Modificaciones de schema de BD que requieren migración
- Cambios arquitectónicos importantes

### Minor (1.X.0)
- Nuevas funcionalidades compatibles hacia atrás
- Nuevos endpoints
- Mejoras de rendimiento significativas

### Patch (1.0.X)
- Corrección de bugs
- Mejoras menores de rendimiento
- Actualizaciones de documentación
- Ajustes de validación

---

## Notas de Migración

### Desde Customer/Supplier Separados
Si vienes de un sistema con entidades separadas, sigue estos pasos:

1. **Backup de datos existentes**
2. **Ejecutar script de migración**:
   ```sql
   -- Migrar customers
   INSERT INTO contacts (name, type, email, company_id, ...)
   SELECT name, ARRAY['client'], email, company_id, ...
   FROM customers;
   
   -- Migrar suppliers  
   INSERT INTO contacts (name, type, email, company_id, ...)
   SELECT name, ARRAY['provider'], email, company_id, ...
   FROM suppliers;
   ```
3. **Actualizar foreign keys** en invoices y bills
4. **Eliminar tablas obsoletas** (después de validar)

### Configuración Requerida
- MinIO configurado para adjuntos
- Redis para cache (opcional pero recomendado)
- Variables de entorno actualizadas

---
