from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from app.modules.email.service import email_service
from app.modules.email.tasks import send_email_task, send_template_email_task
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])

class TestEmailRequest(BaseModel):
    to_email: EmailStr
    subject: str = "Test Email from Ally360"
    message: str = "This is a test email to verify SMTP configuration."

class TestTemplateEmailRequest(BaseModel):
    to_email: EmailStr
    template_name: str = "verification_email.html"
    context: Optional[Dict[str, Any]] = None

@router.post("/test")
async def test_email(request: TestEmailRequest):
    """Test email configuration by sending a simple email"""
    try:
        logger.info(f"Testing email to {request.to_email}")
        
        html_content = f"""
        <html>
        <body>
            <h2>{request.subject}</h2>
            <p>{request.message}</p>
            <p>If you received this email, your SMTP configuration is working correctly.</p>
            <hr>
            <p><small>Sent from Ally360 Email Service</small></p>
        </body>
        </html>
        """
        
        text_content = f"{request.subject}\n\n{request.message}\n\nIf you received this email, your SMTP configuration is working correctly."
        
        result = email_service.send_email(
            to_emails=[request.to_email],
            subject=request.subject,
            html_content=html_content,
            text_content=text_content
        )
        
        if result:
            return {"message": "Test email sent successfully", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test email")
            
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending email: {str(e)}")

@router.post("/test-verification")
async def test_verification_email(request: TestEmailRequest):
    """Test verification email specifically"""
    try:
        logger.info(f"Testing verification email to {request.to_email}")
        
        # Use a dummy token for testing
        test_token = "test-verification-token-123456"
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={test_token}"
        
        context = {
            "verification_url": verification_url,
            "frontend_url": settings.FRONTEND_URL,
            "user_email": request.to_email
        }
        
        result = email_service.send_template_email(
            to_emails=[request.to_email],
            subject="Test - Verificar Email - Ally360",
            template_name="verification_email.html",
            context=context
        )
        
        if result:
            return {
                "message": "Test verification email sent successfully", 
                "success": True,
                "verification_url": verification_url
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send test verification email")
            
    except Exception as e:
        logger.error(f"Error sending test verification email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending verification email: {str(e)}")

@router.post("/test-celery")
async def test_email_via_celery(request: TestEmailRequest):
    """Test email sending through Celery task (checks worker + broker)."""
    try:
        html_content = f"<h2>{request.subject}</h2><p>{request.message}</p>"
        async_result = send_email_task.delay(
            to_emails=[request.to_email],
            subject=f"[CELERY] {request.subject}",
            html_content=html_content,
            text_content=request.message
        )
        return {"message": "Task enqueued", "task_id": async_result.id}
    except Exception as e:
        logger.error(f"Error enqueueing celery email task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error enqueueing task: {str(e)}")

class TestTemplateCeleryRequest(BaseModel):
    to_email: EmailStr
    template_name: str
    context: Optional[Dict[str, Any]] = None
    subject: str = "Template Test"

@router.post("/test-template-celery")
async def test_template_email_via_celery(req: TestTemplateCeleryRequest):
    """Test template email via Celery task."""
    try:
        async_result = send_template_email_task.delay(
            to_emails=[req.to_email],
            subject=f"[CELERY] {req.subject}",
            template_name=req.template_name,
            context=req.context or {}
        )
        return {"message": "Task enqueued", "task_id": async_result.id}
    except Exception as e:
        logger.error(f"Error enqueueing template celery task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error enqueueing task: {str(e)}")

@router.get("/config")
async def get_email_config():
    """Get current email configuration (for debugging)"""
    return {
        "smtp_server": settings.EMAIL_SMTP_SERVER,
        "smtp_port": settings.EMAIL_SMTP_PORT,
        "use_tls": settings.EMAIL_USE_TLS,
        "username": settings.EMAIL_USERNAME,
        "from_email": settings.EMAIL_FROM,
        "from_name": settings.EMAIL_FROM_NAME,
        "frontend_url": settings.FRONTEND_URL
    }

@router.post("/test-raw-smtp")
async def test_raw_smtp(request: TestEmailRequest):
    """Test raw SMTP connection without using the service"""
    import smtplib
    import ssl
    from email.mime.text import MIMEText
    
    try:
        logger.info("Testing raw SMTP connection...")
        
        msg = MIMEText(f"Raw SMTP test message: {request.message}")
        msg['Subject'] = f"RAW SMTP - {request.subject}"
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = request.to_email
        
        logger.info(f"Connecting to {settings.EMAIL_SMTP_SERVER}:{settings.EMAIL_SMTP_PORT}")

        # Match EmailService connection behavior
        if settings.EMAIL_USE_TLS:
            context = ssl.create_default_context()
            server = smtplib.SMTP(settings.EMAIL_SMTP_SERVER, settings.EMAIL_SMTP_PORT)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        else:
            if int(settings.EMAIL_SMTP_PORT) == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(settings.EMAIL_SMTP_SERVER, settings.EMAIL_SMTP_PORT, context=context)
            else:
                server = smtplib.SMTP(settings.EMAIL_SMTP_SERVER, settings.EMAIL_SMTP_PORT)
                server.ehlo()
        
        logger.info(f"Logging in with username: {settings.EMAIL_USERNAME}")
        server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
        
        logger.info(f"Sending email from {settings.EMAIL_FROM} to {request.to_email}")
        server.sendmail(settings.EMAIL_FROM, [request.to_email], msg.as_string())
        server.quit()
        
        return {"message": "Raw SMTP test successful", "success": True}
        
    except Exception as e:
        logger.error(f"Raw SMTP test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Raw SMTP test failed: {str(e)}")