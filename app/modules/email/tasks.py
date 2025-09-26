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