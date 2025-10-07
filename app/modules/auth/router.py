from fastapi import APIRouter, HTTPException, Depends, status, Request, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from app.dependencies.dbDependecies import get_db
from app.modules.auth.service import AuthService
from app.modules.auth.dependencies import get_current_user, get_auth_context, require_owner_or_admin
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    UserCreate, UserLogin, UserOut, TokenResponse, ContextTokenResponse,
    EmailVerificationRequest, EmailVerificationConfirm, EmailVerificationWithAutoLogin, EmailVerificationResponse,
    PasswordResetRequest, PasswordResetConfirm,
    CompanyInvitationCreate, CompanyInvitationOut, CompanyInvitationAccept,
    CompanyInvitationAcceptExisting, InvitationInfo,
    CompanySelectionRequest, AuthContext, RefreshTokenRequest,
    UserUpdate, UserFirstLoginUpdate, ImageUploadResponse, CompanyUsersResponse
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

@auth_router.post("/verify-email", response_model=EmailVerificationResponse)
async def verify_email(verification_data: EmailVerificationWithAutoLogin, db: Session = Depends(get_db)):
    """
    Verificar email con token.
    Si auto_login=true, genera tokens de acceso automáticamente para un flujo sin interrupciones.
    """
    auth_service = AuthService(db)
    result = auth_service.verify_email_with_auto_login(
        token=verification_data.token,
        auto_login=verification_data.auto_login
    )
    
    return EmailVerificationResponse(**result)

@auth_router.get("/verify-email", response_model=EmailVerificationResponse)
async def verify_email_get(
    token: str,
    auto_login: bool = False,
    db: Session = Depends(get_db)
):
    """
    Verificar email via GET (para links en correos).
    Si auto_login=true, genera tokens de acceso automáticamente.
    """
    auth_service = AuthService(db)
    result = auth_service.verify_email_with_auto_login(
        token=token,
        auto_login=auto_login
    )
    
    return EmailVerificationResponse(**result)

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

@auth_router.post("/accept-invitation/existing", response_model=dict)
async def accept_company_invitation_existing_user(
    acceptance_data: CompanyInvitationAcceptExisting,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Aceptar invitación a empresa para usuario ya autenticado.
    """
    auth_service = AuthService(db)
    company = auth_service.accept_invitation_existing_user(
        token=acceptance_data.token,
        user_id=current_user.id
    )
    
    return {
        "message": "Te has unido a la empresa exitosamente",
        "company_id": str(company.id),
        "company_name": company.name
    }

@auth_router.get("/invitation/{token}", response_model=InvitationInfo)
async def get_invitation_info(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Obtener información sobre una invitación.
    Útil para que el frontend determine si el usuario debe registrarse o solo aceptar.
    """
    auth_service = AuthService(db)
    info = auth_service.get_invitation_info(token)
    return InvitationInfo(**info)

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

@auth_router.get("/company/users", response_model=CompanyUsersResponse)
async def get_company_users(
    page: int = 1,
    limit: int = 25,
    auth_context: AuthContext = Depends(require_owner_or_admin()),
    db: Session = Depends(get_db)
):
    """
    Obtener lista de usuarios de la empresa con paginación.
    Requiere rol de owner o admin.
    """
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere seleccionar una empresa"
        )
    
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La página debe ser mayor a 0"
        )
    
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El límite debe estar entre 1 y 100"
        )
    
    auth_service = AuthService(db)
    result = auth_service.get_company_users(
        company_id=auth_context.tenant_id,
        page=page,
        limit=limit
    )
    
    return CompanyUsersResponse(**result)

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


@auth_router.patch("/me/first-login", response_model=UserOut)
async def update_first_login(
    first_login_update: UserFirstLoginUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar el estado de first_login del usuario.
    Usado cuando el usuario completa el onboarding/step-by-step.
    """
    auth_service = AuthService(db)
    updated_user = auth_service.update_first_login(current_user.id, first_login_update.first_login)
    return UserOut.from_orm(updated_user)


@auth_router.patch("/me", response_model=UserOut)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar información del perfil del usuario actual.
    No permite cambiar DNI.
    """
    auth_service = AuthService(db)
    return auth_service.update_user_profile(current_user.id, user_update)


@auth_router.post("/me/avatar", response_model=ImageUploadResponse)
async def upload_user_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...)
):
    """
    Subir avatar del usuario actual.
    """
    auth_service = AuthService(db)
    return auth_service.upload_user_avatar(current_user.id, file)

@auth_router.get("/me/avatar")
async def get_user_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener URL temporal para acceder al avatar del usuario actual.
    """
    auth_service = AuthService(db)
    return auth_service.get_user_avatar_url(current_user.id)

@auth_router.get("/health")
def auth_health():
    """Health check for auth module"""
    return {"status": "ok", "module": "auth"}
