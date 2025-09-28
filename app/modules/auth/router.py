from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from app.dependencies.dbDependecies import get_db
from app.modules.auth.service import AuthService
from app.modules.auth.dependencies import get_current_user, get_auth_context, require_owner_or_admin
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    UserCreate, UserLogin, UserOut, TokenResponse, ContextTokenResponse,
    EmailVerificationRequest, EmailVerificationConfirm,
    PasswordResetRequest, PasswordResetConfirm,
    CompanyInvitationCreate, CompanyInvitationOut, CompanyInvitationAccept,
    CompanySelectionRequest, AuthContext, RefreshTokenRequest
)

auth_router = APIRouter()

@auth_router.post("/register", response_model=dict)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Registrar nuevo usuario con verificación de email.
    """
    auth_service = AuthService(db)
    user, verification_token = auth_service.create_user(user_data)
    
    return {
        "message": "Usuario registrado exitosamente",
        "email": user.email,
        "verification_required": True,
        "user_id": str(user.id)
    }

@auth_router.post("/verify-email", response_model=dict)
async def verify_email(verification_data: EmailVerificationConfirm, db: Session = Depends(get_db)):
    """
    Verificar email con token.
    """
    auth_service = AuthService(db)
    user = auth_service.verify_email(verification_data.token)
    
    return {
        "message": "Email verificado exitosamente",
        "user_id": str(user.id),
        "is_active": user.is_active
    }

@auth_router.post("/resend-verification", response_model=dict)
async def resend_verification_email(request_data: EmailVerificationRequest, db: Session = Depends(get_db)):
    """
    Reenviar email de verificación.
    """
    auth_service = AuthService(db)
    auth_service.resend_verification(request_data.email)
    return {"message": "Email de verificación enviado"}

@auth_router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login de usuario. Retorna token de acceso y lista de empresas.
    """
    auth_service = AuthService(db)
    return auth_service.login(form_data.username, form_data.password)

@auth_router.post("/select-company", response_model=ContextTokenResponse)
async def select_company(
    selection_data: CompanySelectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Seleccionar empresa y obtener token de contexto.
    """
    auth_service = AuthService(db)
    return auth_service.select_company(current_user.id, selection_data.company_id)

@auth_router.get("/me", response_model=UserOut)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Obtener información del usuario actual.
    """
    return UserOut.from_orm(current_user)

@auth_router.get("/context")
async def get_auth_context_info(auth_context: AuthContext = Depends(get_auth_context)):
    """
    Obtener contexto de autenticación completo.
    """
    return {
        "user_id": auth_context.user_id,
        "tenant_id": auth_context.tenant_id,
        "user_role": auth_context.user_role,
        "companies": auth_context.companies
    }

@auth_router.post("/request-password-reset", response_model=dict)
async def request_password_reset(
    request_data: PasswordResetRequest, 
    db: Session = Depends(get_db)
):
    """
    Solicitar restablecimiento de contraseña.
    """
    auth_service = AuthService(db)
    auth_service.request_password_reset(request_data.email)
    
    return {
        "message": "Si el email existe, se enviará un enlace de restablecimiento"
    }

@auth_router.post("/reset-password", response_model=dict)
async def reset_password(
    reset_data: PasswordResetConfirm, 
    db: Session = Depends(get_db)
):
    """
    Restablecer contraseña con token.
    """
    auth_service = AuthService(db)
    user = auth_service.reset_password(reset_data.token, reset_data.new_password)
    
    return {
        "message": "Contraseña restablecida exitosamente",
        "user_id": str(user.id)
    }

@auth_router.post("/invite-user", response_model=dict)
async def invite_user_to_company(
    invitation_data: CompanyInvitationCreate,
    auth_context: AuthContext = Depends(require_owner_or_admin()),
    db: Session = Depends(get_db)
):
    """
    Invitar usuario a empresa (solo owners/admins).
    """
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere seleccionar una empresa"
        )
    
    auth_service = AuthService(db)
    invitation = auth_service.invite_user(
        company_id=auth_context.tenant_id,
        invited_by_id=auth_context.user_id,
        invitation_data=invitation_data
    )
    
    return {
        "message": "Invitación enviada exitosamente",
        "invitation_id": str(invitation.id),
        "expires_at": invitation.expires_at
    }

@auth_router.post("/accept-invitation", response_model=dict)
async def accept_company_invitation(
    acceptance_data: CompanyInvitationAccept,
    db: Session = Depends(get_db)
):
    """
    Aceptar invitación a empresa.
    """
    auth_service = AuthService(db)
    user, company = auth_service.accept_invitation(
        token=acceptance_data.token,
        password=acceptance_data.password,
        profile_data=acceptance_data.profile.dict()
    )
    
    return {
        "message": "Invitación aceptada exitosamente",
        "user_id": str(user.id),
        "company_id": str(company.id),
        "company_name": company.name
    }

@auth_router.get("/invitations", response_model=List[CompanyInvitationOut])
async def get_pending_invitations(
    auth_context: AuthContext = Depends(require_owner_or_admin()),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """
    Obtener invitaciones pendientes de la empresa.
    """
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere seleccionar una empresa"
        )
    
    auth_service = AuthService(db)
    return auth_service.list_invitations(company_id=auth_context.tenant_id, limit=limit, offset=offset)

@auth_router.post("/logout", response_model=dict)
async def logout():
    """
    Logout (del lado cliente, invalidar token).
    """
    return {"message": "Logout exitoso"}

@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Renovar token de acceso con refresh token.
    """
    auth_service = AuthService(db)
    return auth_service.refresh_access_token(body.refresh_token)

@auth_router.get("/health")
def auth_health():
    """Health check for auth module"""
    return {"status": "ok", "module": "auth"}
