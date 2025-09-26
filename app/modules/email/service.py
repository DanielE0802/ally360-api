import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from pathlib import Path
import os
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """
    Servicio de correo electrónico con soporte para templates Jinja2.
    """
    
    def __init__(self):
        self.smtp_server = settings.EMAIL_SMTP_SERVER
        self.smtp_port = settings.EMAIL_SMTP_PORT
        self.username = settings.EMAIL_USERNAME
        self.password = settings.EMAIL_PASSWORD
        self.use_tls = settings.EMAIL_USE_TLS
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.EMAIL_FROM_NAME
        self.frontend_url = settings.FRONTEND_URL
        
        # Setup Jinja2 environment for email templates
        template_dir = Path(__file__).parent / "templates"
        template_dir.mkdir(exist_ok=True)
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def _create_smtp_connection(self):
        """Crear conexión SMTP segura."""
        try:
            if self.use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            
            server.login(self.username, self.password)
            return server
        except Exception as e:
            logger.error(f"Error creating SMTP connection: {str(e)}")
            raise
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Renderizar template de email con contexto.
        
        Args:
            template_name: Nombre del archivo de template
            context: Variables para el template
            
        Returns:
            HTML renderizado del template
        """
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {str(e)}")
            raise
    
    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        """
        Enviar correo electrónico.
        
        Args:
            to_emails: Lista de destinatarios
            subject: Asunto del correo
            html_content: Contenido HTML
            text_content: Contenido de texto plano
            attachments: Lista de rutas de archivos adjuntos
            cc_emails: Lista de destinatarios en copia
            bcc_emails: Lista de destinatarios en copia oculta
            
        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ', '.join(to_emails)
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Add text content
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # Add HTML content
            if html_content:
                html_part = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.isfile(file_path):
                        with open(file_path, "rb") as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                        
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(file_path)}'
                        )
                        msg.attach(part)
            
            # Send email
            with self._create_smtp_connection() as server:
                all_recipients = to_emails[:]
                if cc_emails:
                    all_recipients.extend(cc_emails)
                if bcc_emails:
                    all_recipients.extend(bcc_emails)
                
                server.sendmail(self.from_email, all_recipients, msg.as_string())
            
            logger.info(f"Email sent successfully to {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def send_template_email(
        self,
        to_emails: List[str],
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Enviar correo usando template.
        
        Args:
            to_emails: Lista de destinatarios
            subject: Asunto del correo
            template_name: Nombre del template (ej: "verification_email.html")
            context: Variables para el template
            cc_emails: Lista de destinatarios en copia
            bcc_emails: Lista de destinatarios en copia oculta
            attachments: Lista de archivos adjuntos
            
        Returns:
            True si se envió correctamente
        """
        try:
            html_content = self.render_template(template_name, context)
            
            return self.send_email(
                to_emails=to_emails,
                subject=subject,
                html_content=html_content,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                attachments=attachments
            )
        except Exception as e:
            logger.error(f"Error sending template email: {str(e)}")
            return False

# Singleton instance
email_service = EmailService()