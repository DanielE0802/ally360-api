# Endpoint de Envío de Facturas por Email

## Descripción
Este endpoint permite enviar facturas por email recibiendo el PDF generado desde el frontend.

## Endpoint
```
POST /invoices/{invoice_id}/send-email
```

## Parámetros

### Path Parameters
- `invoice_id` (UUID): ID de la factura a enviar

### Form Data
- `to_email` (string, required): Email del destinatario
- `subject` (string, optional): Asunto personalizado del email
- `message` (string, optional): Mensaje personalizado para incluir en el email
- `pdf_file` (file, required): Archivo PDF de la factura (máximo 10MB)

## Headers Requeridos
```
Authorization: Bearer {token}
X-Company-ID: {tenant_id}
Content-Type: multipart/form-data
```

## Ejemplo de Uso con cURL

```bash
curl -X POST "http://localhost:8000/invoices/{invoice_id}/send-email" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  -H "X-Company-ID: 12345678-1234-1234-1234-123456789012" \
  -F "to_email=cliente@example.com" \
  -F "subject=Su factura de compra" \
  -F "message=Adjuntamos su factura. Gracias por su compra." \
  -F "pdf_file=@/path/to/factura.pdf"
```

## Ejemplo de Uso con JavaScript (Frontend)

```javascript
const sendInvoiceEmail = async (invoiceId, emailData, pdfFile) => {
  const formData = new FormData();
  formData.append('to_email', emailData.toEmail);
  formData.append('subject', emailData.subject || '');
  formData.append('message', emailData.message || '');
  formData.append('pdf_file', pdfFile);

  const response = await fetch(`/api/invoices/${invoiceId}/send-email`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Company-ID': companyId
    },
    body: formData
  });

  if (!response.ok) {
    throw new Error('Error enviando email');
  }

  return await response.json();
};

// Uso
const result = await sendInvoiceEmail(
  'invoice-uuid-here',
  {
    toEmail: 'cliente@example.com',
    subject: 'Su factura de compra',
    message: 'Gracias por su compra'
  },
  pdfFileFromInput
);

console.log(result);
// { "status": "queued", "task_id": "task-id", "message": "Email programado..." }
```

## Respuesta Exitosa

```json
{
  "status": "queued",
  "task_id": "12345678-1234-1234-1234-123456789012",
  "message": "Email de factura F-000001 programado para envío a cliente@example.com"
}
```

## Errores Posibles

### 400 Bad Request
```json
{
  "detail": "El archivo debe ser un PDF válido"
}
```

### 413 Request Entity Too Large
```json
{
  "detail": "El archivo PDF es demasiado grande (máximo 10MB)"
}
```

### 404 Not Found
```json
{
  "detail": "Factura no encontrada"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "to_email"],
      "msg": "String should have at least 1 character"
    }
  ]
}
```

## Proceso de Envío

1. **Validación**: Se valida que el archivo sea PDF y no exceda 10MB
2. **Verificación**: Se verifica que la factura existe y pertenece al tenant
3. **Cola de Tareas**: Se programa el envío usando Celery para procesamiento asíncrono
4. **Template**: Se usa el template `invoice_email.html` para el contenido del email
5. **Adjunto**: Se adjunta el PDF recibido al email
6. **Envío**: Se envía usando la configuración SMTP de la aplicación

## Configuración Requerida

Asegúrate de que las siguientes variables de entorno estén configuradas:

```env
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USE_TLS=true
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_FROM=noreply@ally360.com
EMAIL_FROM_NAME=Ally360 ERP
```

## Estados de la Tarea

- `queued`: El email ha sido programado para envío
- `success`: El email se envió correctamente
- `failed`: El envío falló (se reintenta automáticamente hasta 3 veces)

## Monitoreo

Para monitorear el estado de la tarea, puedes usar el `task_id` retornado con Celery o implementar webhooks para notificaciones de estado.