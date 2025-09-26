"""
Módulo de email para Ally360.
"""

from .service import email_service
from .tasks import (
    send_email_task,
    send_template_email_task,
    send_verification_email_task,
    send_invitation_email_task,
    send_password_reset_email_task
)

__all__ = [
    'email_service',
    'send_email_task',
    'send_template_email_task', 
    'send_verification_email_task',
    'send_invitation_email_task',
    'send_password_reset_email_task'
]