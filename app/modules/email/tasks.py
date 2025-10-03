"""
Tareas asíncronas de Celery para el envío de correos electrónicos.
"""
import logging
from typing import Dict, Any, List, Optional
from celery import current_task
from app.core.celery import celery_app
from app.modules.email.service import email_service

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def send_email_task(
    self,
    to_emails: List[str],
    subject: str,
    html_content: Optional[str] = None,
    text_content: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    attachments: Optional[List[str]] = None
):
    """
    Tarea asíncrona para envío de correos electrónicos.
    """
    try:
        success = email_service.send_email(
            to_emails=to_emails,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            cc_emails=cc_emails,
            bcc_emails=bcc_emails,
            attachments=attachments
        )
        
        if not success:
            raise Exception("Failed to send email")
            
        logger.info(f"Email sent successfully to {', '.join(to_emails)}")
        return {"status": "success", "recipients": to_emails}
        
    except Exception as exc:
        logger.error(f"Email sending failed: {str(exc)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        # Final failure
        return {"status": "failed", "error": str(exc), "recipients": to_emails}

@celery_app.task(bind=True, max_retries=3)
def send_template_email_task(
    self,
    to_emails: List[str],
    subject: str,
    template_name: str,
    context: Dict[str, Any],
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    attachments: Optional[List[str]] = None
):
    """
    Tarea asíncrona para envío de correos con template.
    """
    try:
        success = email_service.send_template_email(
            to_emails=to_emails,
            subject=subject,
            template_name=template_name,
            context=context,
            cc_emails=cc_emails,
            bcc_emails=bcc_emails,
            attachments=attachments
        )
        
        if not success:
            raise Exception("Failed to send template email")
            
        logger.info(f"Template email '{template_name}' sent successfully to {', '.join(to_emails)}")
        return {"status": "success", "template": template_name, "recipients": to_emails}
        
    except Exception as exc:
        logger.error(f"Template email sending failed: {str(exc)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        # Final failure
        return {"status": "failed", "error": str(exc), "template": template_name, "recipients": to_emails}

# Tareas específicas para eventos de autenticación
@celery_app.task(bind=True, max_retries=3)
def send_verification_email_task(
    self,
    user_email: str,
    user_name: str,
    verification_token: str,
    company_name: Optional[str] = None
):
    """
    Enviar correo de verificación de cuenta.
    """
    try:
        verification_url = f"{email_service.frontend_url}/verify-email?token={verification_token}"
        
        context = {
            "user_name": user_name,
            "verification_url": verification_url,
            "company_name": company_name,
            "support_email": email_service.from_email
        }
        
        success = email_service.send_template_email(
            to_emails=[user_email],
            subject="Verifica tu cuenta en Ally360",
            template_name="verification_email.html",
            context=context
        )
        
        if not success:
            raise Exception("Failed to send verification email")
            
        return {"status": "success", "email": user_email}
        
    except Exception as exc:
        logger.error(f"Verification email failed: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        return {"status": "failed", "error": str(exc)}

@celery_app.task(bind=True, max_retries=3)
def send_invitation_email_task(
    self,
    invitee_email: str,
    inviter_name: str,
    company_name: str,
    invitation_token: str,
    role: str
):
    """
    Enviar correo de invitación a empresa.
    """
    try:
        invitation_url = f"{email_service.frontend_url}/accept-invitation?token={invitation_token}"
        
        context = {
            "invitee_email": invitee_email,
            "inviter_name": inviter_name,
            "company_name": company_name,
            "invitation_url": invitation_url,
            "role": role,
            "support_email": email_service.from_email
        }
        
        success = email_service.send_template_email(
            to_emails=[invitee_email],
            subject=f"Te han invitado a {company_name} en Ally360",
            template_name="invitation_email.html",
            context=context
        )
        
        if not success:
            raise Exception("Failed to send invitation email")
            
        return {"status": "success", "email": invitee_email}
        
    except Exception as exc:
        logger.error(f"Invitation email failed: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        return {"status": "failed", "error": str(exc)}

@celery_app.task(bind=True, max_retries=3) 
def send_password_reset_email_task(
    self,
    user_email: str,
    user_name: str,
    reset_token: str
):
    """
    Enviar correo de restablecimiento de contraseña.
    """
    try:
        reset_url = f"{email_service.frontend_url}/reset-password?token={reset_token}"
        
        context = {
            "user_name": user_name,
            "reset_url": reset_url,
            "support_email": email_service.from_email
        }
        
        success = email_service.send_template_email(
            to_emails=[user_email],
            subject="Restablece tu contraseña en Ally360",
            template_name="password_reset_email.html",
            context=context
        )
        
        if not success:
            raise Exception("Failed to send password reset email")
            
        return {"status": "success", "email": user_email}
        
    except Exception as exc:
        logger.error(f"Password reset email failed: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(bind=True, max_retries=3)
def send_invoice_email_task(
    self,
    to_email: str,
    invoice_data: Dict[str, Any],
    company_data: Dict[str, Any],
    pdf_content_b64: str,  # Cambiado a string base64
    pdf_filename: str,
    custom_message: Optional[str] = None,
    subject: Optional[str] = None
):
    """
    Enviar factura por correo electrónico con PDF adjunto.
    
    Args:
        to_email: Email del destinatario
        invoice_data: Datos de la factura (número, fecha, total, etc.)
        company_data: Datos de la empresa
        pdf_content_b64: Contenido del PDF en base64
        pdf_filename: Nombre del archivo PDF
        custom_message: Mensaje personalizado opcional
        subject: Asunto personalizado opcional
    """
    import tempfile
    import os
    import base64
    
    try:
        # Decodificar el PDF de base64 a bytes
        pdf_content = base64.b64decode(pdf_content_b64)
        logger.info(f"PDF decoded successfully: {len(pdf_content)} bytes")
        
        # Crear archivo temporal para el PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_content)
            tmp_pdf_path = tmp_file.name
        
        logger.info(f"PDF temporary file created at: {tmp_pdf_path}")
        
        # Verificar que el archivo existe y tiene contenido
        if not os.path.exists(tmp_pdf_path):
            raise Exception(f"Temporary PDF file was not created: {tmp_pdf_path}")
        
        file_size = os.path.getsize(tmp_pdf_path)
        logger.info(f"PDF file size on disk: {file_size} bytes")
        
        try:
            # Preparar contexto para el template
            context = {
                "company_name": company_data.get("name", "Su Empresa"),
                "company_phone": company_data.get("phone"),
                "company_email": company_data.get("email"),
                "customer_name": invoice_data.get("customer_name", "Cliente"),
                "invoice_number": invoice_data.get("number", "N/A"),
                "invoice_date": invoice_data.get("issue_date", ""),
                "due_date": invoice_data.get("due_date"),
                "total_amount": f"{invoice_data.get('total_amount', 0):,.2f}",
                "balance_due": invoice_data.get('balance_due', 0),
                "custom_message": custom_message,
                "payment_url": invoice_data.get("payment_url"),  # URL para ver factura online
            }
            
            # Generar asunto si no se proporcionó uno
            if not subject:
                subject = f"Factura {invoice_data.get('number', 'N/A')} - {company_data.get('name', 'Su Empresa')}"
            
            logger.info(f"Sending invoice email to {to_email} with PDF attachment ({len(pdf_content)} bytes)")
            logger.info(f"Template context prepared: {context}")
            logger.info(f"PDF attachment path: {tmp_pdf_path}")
            
            # Enviar email con template y adjunto
            success = email_service.send_template_email(
                to_emails=[to_email],
                subject=subject,
                template_name="invoice_email.html",
                context=context,
                attachments=[tmp_pdf_path]
            )
            
            if not success:
                raise Exception("Failed to send invoice email")
                
            logger.info(f"Invoice email sent successfully to {to_email}")
            return {
                "status": "success", 
                "recipient": to_email, 
                "invoice_number": invoice_data.get('number')
            }
            
        finally:
            # Limpiar archivo temporal
            try:
                os.unlink(tmp_pdf_path)
            except Exception:
                pass
        
    except Exception as exc:
        logger.error(f"Invoice email sending failed to {to_email}: {str(exc)}", exc_info=True)
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying invoice email task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        # Final failure
        logger.error(f"Invoice email task failed permanently after {self.max_retries} retries")
        return {
            "status": "failed", 
            "error": str(exc), 
            "recipient": to_email,
            "invoice_number": invoice_data.get('number')
        }