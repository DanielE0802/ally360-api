import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from uuid import UUID, uuid4
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_

from app.modules.auth.models import (
    User, Profile, UserCompany, EmailVerificationToken, 
    PasswordResetToken, CompanyInvitation
)
from app.modules.auth.schemas import (
    UserCreate, UserOut, TokenResponse, ContextTokenResponse,
    CompanyInvitationCreate, AuthContext, UserCompanyOut
)
from app.modules.auth.utils import (
    hash_password, verify_password, create_access_token, 
    create_context_token, create_refresh_token, verify_token
)
from app.modules.company.models import Company
from app.modules.email.tasks import (
    send_verification_email_task, send_invitation_email_task, 
    send_password_reset_email_task
)
from app.core.config import settings

class AuthService:
    """
    Servicio de autenticación multi-tenant completo.
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generar token seguro aleatorio usando secrets module.
        
        Args:
            length: Longitud del token (default: 32)
            
        Returns:
            str: Token seguro alfanumérico
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def create_user(self, user_data: UserCreate) -> Tuple[User, str]:
        """
        Crear nuevo usuario con verificación de email.
        
        Returns:
            Tuple[User, str]: Usuario creado y token de verificación
        """
        # Verificar si el email ya existe
        existing_user = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este email ya está registrado"
            )

        # Crear perfil
        profile = Profile(
            first_name=user_data.profile.first_name,
            last_name=user_data.profile.last_name,
            phone_number=user_data.profile.phone_number,
            dni=user_data.profile.dni
        )
        self.db.add(profile)
        self.db.flush()

        # Crear usuario
        hashed_password = hash_password(user_data.password)
        user = User(
            email=user_data.email,
            password=hashed_password,
            profile_id=profile.id,
            is_active=False,
            email_verified=False
        )
        self.db.add(user)
        self.db.flush()

        # Paso 1: Solo crear usuario (la empresa se crea y asocia en un paso posterior)

        # Generar token de verificación
        verification_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        email_token = EmailVerificationToken(
            user_id=user.id,
            token=verification_token,
            expires_at=expires_at
        )
        self.db.add(email_token)
        self.db.commit()

        # Enviar email de verificación (asíncrono)
        send_verification_email_task.delay(
            user_email=user.email,
            user_name=user.profile.first_name,
            verification_token=verification_token,
            company_name=None,
            auto_login=True  # Por defecto, habilitar auto-login
        )

        return user, verification_token

    def verify_email(self, token: str) -> User:
        """Verificar email con token."""
        email_token = self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token == token,
            EmailVerificationToken.is_used == False,
            EmailVerificationToken.expires_at > datetime.now(timezone.utc)
        ).first()

        if not email_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de verificación inválido o expirado"
            )

        # Marcar token como usado
        email_token.is_used = True
        email_token.used_at = datetime.now(timezone.utc)

        # Activar usuario
        user = email_token.user
        user.is_active = True
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)

        self.db.commit()
        return user

    def verify_email_with_auto_login(self, token: str, auto_login: bool = False) -> dict:
        """
        Verificar email con opción de auto-login.
        Si auto_login=True, genera tokens de acceso automáticamente.
        """
        # Verificar email normalmente
        user = self.verify_email(token)
        
        response = {
            "message": "Email verificado exitosamente",
            "user_id": str(user.id),
            "is_active": user.is_active
        }
        
        if auto_login:
            # Buscar si el usuario pertenece a alguna empresa
            user_company = self.db.query(UserCompany).filter(
                UserCompany.user_id == user.id,
                UserCompany.is_active == True
            ).first()
            
            tenant_id = user_company.company_id if user_company else None
            
            # Generar tokens
            access_token_data = {
                "sub": str(user.id),
                "email": user.email,
                "user_name": user.profile.full_name if user.profile else user.email,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "type": "access"
            }
            
            access_token = create_access_token(data=access_token_data)
            refresh_token = create_refresh_token(user_id=str(user.id))
            
            response.update({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": 1800000,  # 30 minutes in milliseconds
                "tenant_id": str(tenant_id) if tenant_id else None,
                "message": "Email verificado y sesión iniciada automáticamente"
            })
        
        return response

    def resend_verification(self, email: str) -> bool:
        """Reenviar email de verificación si el usuario aún no ha verificado."""
        user = self.db.query(User).options(selectinload(User.profile)).filter(User.email == email).first()
        if not user:
            # No revelar existencia
            return True

        if user.email_verified and user.is_active:
            # Ya verificado; no es necesario reenviar
            return True

        # Invalidar tokens anteriores no usados
        self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.is_used == False
        ).update({"is_used": True})

        # Crear nuevo token
        verification_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        token_record = EmailVerificationToken(
            user_id=user.id,
            token=verification_token,
            expires_at=expires_at
        )
        self.db.add(token_record)
        self.db.commit()

        # Enviar email (asíncrono)
        send_verification_email_task.delay(
            user_email=user.email,
            user_name=user.profile.first_name if user.profile else user.email,
            verification_token=verification_token,
            company_name=None,
            auto_login=True  # Por defecto, habilitar auto-login
        )
        return True

    def send_verification_email(self, user_id: UUID, auto_login: bool = True) -> bool:
        """
        Enviar email de verificación con control de auto_login.
        Útil para casos específicos donde se quiere controlar el comportamiento.
        """
        user = self.db.query(User).options(selectinload(User.profile)).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        if user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está verificado"
            )
        
        # Generar nuevo token
        verification_token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        
        # Limpiar tokens anteriores
        self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.is_used == False
        ).update({"is_used": True, "used_at": datetime.now(timezone.utc)})
        
        # Crear nuevo token
        email_token = EmailVerificationToken(
            user_id=user.id,
            token=verification_token,
            expires_at=expires_at
        )
        self.db.add(email_token)
        self.db.commit()
        
        # Enviar email con auto_login controlado
        send_verification_email_task.delay(
            user_email=user.email,
            user_name=user.profile.first_name if user.profile else user.email,
            verification_token=verification_token,
            company_name=None,
            auto_login=auto_login
        )
        
        return True

    def login(self, email: str, password: str) -> TokenResponse:
        """
        Login de usuario con listado de empresas.
        """
        user = self.db.query(User).options(
            selectinload(User.profile),
            selectinload(User.user_companies).selectinload(UserCompany.company)
        ).filter(User.email == email).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )

        if not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta inactiva. Verifica tu email."
            )

        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email no verificado. Revisa tu bandeja de entrada."
            )

        # Actualizar último login
        user.last_login = datetime.now(timezone.utc)
        self.db.commit()

        # Crear token de acceso (sin tenant_id aún)
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "user_name": user.profile.full_name
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(str(user.id))

        # Obtener empresas del usuario
        companies = []
        for uc in user.user_companies:
            if uc.is_active:
                companies.append(UserCompanyOut(
                    id=uc.id,
                    company_id=uc.company_id,
                    role=uc.role,
                    is_active=uc.is_active,
                    joined_at=uc.joined_at,
                    company_name=uc.company.name
                ))

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserOut.from_orm(user),
            companies=companies,
            refresh_token=refresh_token
        )

    def select_company(self, user_id: UUID, company_id: UUID) -> ContextTokenResponse:
        """
        Seleccionar empresa y generar token de contexto.
        """
        user_company = self.db.query(UserCompany).options(
            selectinload(UserCompany.company),
            selectinload(UserCompany.user).selectinload(User.profile)
        ).filter(
            UserCompany.user_id == user_id,
            UserCompany.company_id == company_id,
            UserCompany.is_active == True
        ).first()

        if not user_company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta empresa"
            )

        # Crear token de contexto con tenant_id
        token_data = {
            "sub": str(user_id),
            "email": user_company.user.email,
            "user_name": user_company.user.profile.full_name,
            "tenant_id": str(company_id),
            "user_role": user_company.role
        }
        
        context_token = create_context_token(token_data)

        return ContextTokenResponse(
            access_token=context_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            tenant_id=company_id,
            company_name=user_company.company.name,
            user_role=user_company.role
        )

    def request_password_reset(self, email: str) -> bool:
        """Solicitar restablecimiento de contraseña."""
        user = self.db.query(User).options(
            selectinload(User.profile)
        ).filter(User.email == email).first()

        if not user:
            # No revelar si el email existe o no
            return True

        # Invalidar tokens anteriores
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False
        ).update({"is_used": True})

        # Crear nuevo token
        reset_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token_record = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            expires_at=expires_at
        )
        self.db.add(token_record)
        self.db.commit()

        # Enviar email (asíncrono)
        send_password_reset_email_task.delay(
            user_email=user.email,
            user_name=user.profile.first_name,
            reset_token=reset_token
        )

        return True

    def reset_password(self, token: str, new_password: str) -> User:
        """Restablecer contraseña con token."""
        reset_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc)
        ).first()

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de restablecimiento inválido o expirado"
            )

        # Actualizar contraseña
        user = reset_token.user
        user.password = hash_password(new_password)

        # Marcar token como usado
        reset_token.is_used = True
        reset_token.used_at = datetime.now(timezone.utc)

        self.db.commit()
        return user

    def invite_user(
        self, 
        company_id: UUID, 
        invited_by_id: UUID, 
        invitation_data: CompanyInvitationCreate
    ) -> CompanyInvitation:
        """Invitar usuario a empresa."""
        # Verificar que quien invita tiene permisos
        inviter_company = self.db.query(UserCompany).filter(
            UserCompany.user_id == invited_by_id,
            UserCompany.company_id == company_id,
            UserCompany.role.in_(["owner", "admin"]),
            UserCompany.is_active == True
        ).first()

        if not inviter_company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para invitar usuarios"
            )

        # Verificar si ya existe usuario con ese email en la empresa
        existing_user = self.db.query(User).filter(User.email == invitation_data.email).first()
        if existing_user:
            existing_relation = self.db.query(UserCompany).filter(
                UserCompany.user_id == existing_user.id,
                UserCompany.company_id == company_id
            ).first()
            if existing_relation:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este usuario ya pertenece a la empresa"
                )

        # Verificar si ya existe invitación pendiente
        existing_invitation = self.db.query(CompanyInvitation).filter(
            CompanyInvitation.company_id == company_id,
            CompanyInvitation.invitee_email == invitation_data.email,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).first()

        if existing_invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una invitación pendiente para este email"
            )

        # Crear invitación
        invitation_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        invitation = CompanyInvitation(
            company_id=company_id,
            invited_by_id=invited_by_id,
            invitee_email=invitation_data.email,
            role=invitation_data.role,
            token=invitation_token,
            expires_at=expires_at
        )
        self.db.add(invitation)
        self.db.commit()

        # Obtener datos para el email
        company = self.db.query(Company).filter(Company.id == company_id).first()
        inviter = self.db.query(User).options(selectinload(User.profile)).filter(User.id == invited_by_id).first()

        # Enviar email (asíncrono)
        send_invitation_email_task.delay(
            invitee_email=invitation_data.email,
            inviter_name=inviter.profile.full_name,
            company_name=company.name,
            invitation_token=invitation_token,
            role=invitation_data.role
        )

        return invitation

    def accept_invitation(self, token: str, password: str, profile_data: dict) -> Tuple[User, Company]:
        """Aceptar invitación y crear usuario."""
        invitation = self.db.query(CompanyInvitation).options(
            selectinload(CompanyInvitation.company)
        ).filter(
            CompanyInvitation.token == token,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).first()

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitación inválida o expirada"
            )

        # Verificar si ya existe usuario con ese email
        existing_user = self.db.query(User).filter(User.email == invitation.invitee_email).first()
        
        if existing_user:
            # Si el usuario ya existe, solo crear la relación
            user = existing_user
        else:
            # Crear nuevo usuario
            profile = Profile(**profile_data)
            self.db.add(profile)
            self.db.flush()

            user = User(
                email=invitation.invitee_email,
                password=hash_password(password),
                profile_id=profile.id,
                is_active=True,
                email_verified=True,
                email_verified_at=datetime.now(timezone.utc)
            )
            self.db.add(user)
            self.db.flush()

        # Crear relación usuario-empresa
        user_company = UserCompany(
            user_id=user.id,
            company_id=invitation.company_id,
            role=invitation.role,
            is_active=True
        )
        self.db.add(user_company)

        # Marcar invitación como aceptada
        invitation.is_accepted = True
        invitation.accepted_at = datetime.now(timezone.utc)

        self.db.commit()
        return user, invitation.company

    def accept_invitation_existing_user(self, token: str, user_id: UUID) -> Company:
        """Accept invitation for existing authenticated user."""
        invitation = self.db.query(CompanyInvitation).options(
            selectinload(CompanyInvitation.company)
        ).filter(
            CompanyInvitation.token == token,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).first()

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitación inválida o expirada"
            )

        # Verificar que el usuario actual es el invitado
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or user.email != invitation.invitee_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Esta invitación no corresponde a tu cuenta"
            )

        # Verificar si ya existe la relación usuario-empresa
        existing_relation = self.db.query(UserCompany).filter(
            UserCompany.user_id == user_id,
            UserCompany.company_id == invitation.company_id
        ).first()

        if existing_relation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya eres miembro de esta empresa"
            )

        # Crear relación usuario-empresa
        user_company = UserCompany(
            user_id=user_id,
            company_id=invitation.company_id,
            role=invitation.role,
            is_active=True
        )
        self.db.add(user_company)

        # Marcar invitación como aceptada
        invitation.is_accepted = True
        invitation.accepted_at = datetime.now(timezone.utc)

        self.db.commit()
        return invitation.company

    def get_invitation_info(self, token: str) -> dict:
        """Get information about an invitation token."""
        invitation = self.db.query(CompanyInvitation).options(
            selectinload(CompanyInvitation.company)
        ).filter(
            CompanyInvitation.token == token,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).first()

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitación inválida o expirada"
            )

        # Check if user already exists
        existing_user = self.db.query(User).filter(User.email == invitation.invitee_email).first()

        return {
            "company_name": invitation.company.name,
            "company_id": invitation.company_id,
            "invitee_email": invitation.invitee_email,
            "role": invitation.role,
            "user_exists": existing_user is not None,
            "expires_at": invitation.expires_at
        }

    def list_invitations(
        self,
        company_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> list:
        """Listar invitaciones pendientes por empresa (paginadas)."""
        query = self.db.query(CompanyInvitation).options(
            selectinload(CompanyInvitation.company),
            selectinload(CompanyInvitation.invited_by).selectinload(User.profile)
        ).filter(
            CompanyInvitation.company_id == company_id,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).order_by(CompanyInvitation.created_at.desc())

        invitations = query.offset(offset).limit(min(limit, 100)).all()

        results = []
        for inv in invitations:
            results.append({
                "id": inv.id,
                "invitee_email": inv.invitee_email,
                "role": inv.role,
                "expires_at": inv.expires_at,
                "is_accepted": inv.is_accepted,
                "invited_by_name": inv.invited_by.profile.full_name if inv.invited_by and inv.invited_by.profile else "",
                "company_name": inv.company.name if inv.company else ""
            })
        return results

    def get_company_users(
        self,
        company_id: UUID,
        page: int = 1,
        limit: int = 25
    ) -> dict:
        """Get all users from a company with pagination."""
        offset = (page - 1) * limit
        
        # Query to get users in the company with their profile and role
        query = self.db.query(User, UserCompany).join(
            UserCompany, User.id == UserCompany.user_id
        ).options(
            selectinload(User.profile)
        ).filter(
            UserCompany.company_id == company_id
        ).order_by(User.created_at.desc())
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        results = query.offset(offset).limit(limit).all()
        
        # Format the response
        users = []
        for user, user_company in results:
            users.append({
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "email_verified": user.email_verified,
                "profile": user.profile,
                "role": user_company.role,
                "is_user_active": user_company.is_active,
                "joined_at": user_company.created_at
            })
        
        total_pages = (total + limit - 1) // limit
        
        return {
            "users": users,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        }

    def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Generar un nuevo access token a partir de un refresh token válido."""
        payload = verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token no es de tipo refresh")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token inválido")

        # Cargar usuario y empresas
        user = self.db.query(User).options(
            selectinload(User.profile),
            selectinload(User.user_companies).selectinload(UserCompany.company)
        ).filter(User.id == user_id).first()

        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inválido")

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "user_name": user.profile.full_name if user.profile else user.email
        }
        access_token = create_access_token(token_data)

        companies = []
        for uc in user.user_companies:
            if uc.is_active:
                companies.append(UserCompanyOut(
                    id=uc.id,
                    company_id=uc.company_id,
                    role=uc.role,
                    is_active=uc.is_active,
                    joined_at=uc.joined_at,
                    company_name=uc.company.name
                ))

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserOut.from_orm(user),
            companies=companies
        )

    def update_user_profile(self, user_id: UUID, user_update) -> UserOut:
        """
        Update user profile information.
        DNI cannot be updated.
        """
        user = self.db.query(User).options(selectinload(User.profile)).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        if user_update.profile:
            profile = user.profile
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Perfil no encontrado"
                )

            # Update only provided fields, excluding DNI
            if user_update.profile.first_name is not None:
                profile.first_name = user_update.profile.first_name
            if user_update.profile.last_name is not None:
                profile.last_name = user_update.profile.last_name
            if user_update.profile.phone_number is not None:
                profile.phone_number = user_update.profile.phone_number

            self.db.commit()
            self.db.refresh(user)

        return UserOut.from_orm(user)

    def upload_user_avatar(self, user_id: UUID, file):
        """
        Upload user avatar to MinIO and update profile.
        """
        from app.modules.files.service import upload_file_to_minio
        import uuid

        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permiten archivos de imagen"
            )

        # Get user profile
        user = self.db.query(User).options(selectinload(User.profile)).filter(User.id == user_id).first()
        if not user or not user.profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario o perfil no encontrado"
            )

        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        unique_filename = f"avatar_{uuid.uuid4()}.{file_extension}"
        file_key = f"avatars/{user_id}/{unique_filename}"

        try:
            # Upload to MinIO
            file_url = upload_file_to_minio(
                file=file,
                bucket_name="ally360",
                object_key=file_key
            )

            # Update profile avatar_url
            user.profile.avatar_url = file_url
            self.db.commit()

            return {
                "message": "Avatar subido exitosamente",
                "avatar_url": file_url
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al subir avatar: {str(e)}"
            )

    def get_user_avatar_url(self, user_id: UUID) -> dict:
        """
        Obtener URL temporal (presigned) para acceder al avatar del usuario.
        """
        try:
            user = self.db.query(User).options(
                selectinload(User.profile)
            ).filter(User.id == user_id).first()

            if not user or not user.profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario o perfil no encontrado"
                )

            if not user.profile.avatar_url:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El usuario no tiene avatar"
                )

            # Extraer la key de MinIO desde la URL almacenada
            # La URL almacenada es algo como: http://localhost:9000/ally360/avatars/...
            # Necesitamos extraer solo la parte: avatars/...
            avatar_url = user.profile.avatar_url
            if "/ally360/" in avatar_url:
                object_key = avatar_url.split("/ally360/", 1)[1]
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="URL de avatar inválida"
                )

            from app.modules.files.service import get_presigned_download_url
            
            # Generar URL temporal válida por 1 hora
            presigned_url = get_presigned_download_url(
                bucket_name="ally360",
                object_key=object_key,
                expires_in_hours=1
            )

            return {
                "avatar_url": presigned_url,
                "expires_in": "1 hour"
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener avatar: {str(e)}"
            )

    def update_first_login(self, user_id: UUID, first_login: bool) -> User:
        """
        Update user's first_login status.
        Used when user completes onboarding/step-by-step process.
        
        Args:
            user_id: ID of the user to update
            first_login: New first_login status (typically False after onboarding)
            
        Returns:
            User: Updated user object
        """
        user = self.db.query(User).options(selectinload(User.profile)).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        user.first_login = first_login
        user.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

