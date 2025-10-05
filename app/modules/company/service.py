from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from app.modules.company.schemas import CompanyCreate, CompanyOutWithRole, AssignUserToCompany
from app.modules.auth.utils import create_access_token
from app.dependencies.dbDependecies import db_dependency
from app.modules.auth.models import User, UserCompany
from app.modules.company.models import Company
from uuid import UUID

def create_company(db: db_dependency, company_data: CompanyCreate, current_user: User) -> Company:
    """
    Create a new company in the database.

    Args:
        company_data (CompanyCreate): The company data to create.

    Returns:
        Company: The created company object.
    """

    if db.query(Company).filter_by(name=company_data.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name already exists")

    company = Company(**company_data.model_dump())
    db.add(company)
    db.flush()

    user_company = UserCompany(user_id=current_user.id, company_id=company.id, is_active=True, role="admin")
    db.add(user_company)
    db.commit()
    db.refresh(company)

    return company

def assign_user_to_company(db: db_dependency, assignment: AssignUserToCompany) -> dict:
    """
    Assign a user to a company with a specific role.

    Args:
        user_id (str): The ID of the user to assign.
        company_id (str): The ID of the company to assign the user to.
        role (str): The role of the user in the company.

    Returns:
        UserCompany: The UserCompany object representing the assignment.

    Raises:
        HTTPException: If the user or company does not exist, or if the assignment already exists.
    """
    
    existing_assignment = db.query(UserCompany).filter_by(user_id=assignment.user_id, company_id=assignment.company_id).first()
    if existing_assignment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already assigned to this company")

    company = db.query(Company).filter_by(id=assignment.company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    relation = UserCompany(
        user_id=assignment.user_id,
        company_id=assignment.company_id,
        role=assignment.role
    )

    db.add(relation)
    db.commit()

    return {"message": "User assigned to company successfully", "user_company": relation}

def get_companies_for_user(db: db_dependency, user_id: UUID) -> list[CompanyOutWithRole]:
    """
    Get all companies associated with a user.

    Args:
        db (db_dependency): The database session.
        user (User): The user for whom to retrieve companies.

    Returns:
        list[CompanyOutWithRole]: A list of companies associated with the user.
    """

    all_user_companies = db.query(UserCompany).filter_by(user_id=user_id, is_active=True).all()
    if not all_user_companies:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No companies found for this user")
    return [
        CompanyOutWithRole(
            **vars(user_company.company),
            role=str(user_company.role)
        )
        for user_company in all_user_companies
    ]
    
def select_company(db: db_dependency, company_id: UUID, current_user: User):
    """
    Select a company for the current user and return new access token with company context.
    """

    user_company = db.query(UserCompany).filter_by(user_id=current_user.id, company_id=company_id).first()
    if not user_company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Don't have access to this company")

    token = create_access_token({
        "email": current_user.email,
        "first_name": current_user.profile.first_name,
        "role": user_company.role,
        "company_id": str(user_company.company_id),
        "sub": str(current_user.id)
    })
    
    return {"access_token": token, "token_type": "bearer"}

def create_tenant_company(db: Session, name: str, owner_id: UUID) -> Company:
    """
    Crear nueva empresa para multi-tenant con configuración completa.
    
    Args:
        db: Sesión de base de datos
        name: Nombre de la empresa
        owner_id: ID del usuario propietario
        
    Returns:
        Company: Empresa creada
    """
    # Verificar que no exista una empresa con el mismo nombre
    existing_company = db.query(Company).filter(Company.name == name).first()
    if existing_company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una empresa con este nombre"
        )
    
    # Crear la empresa
    from uuid import uuid4
    company = Company(
        name=name,
        description=f"Empresa creada para {name}",
        is_active=True,
        nit=f"NIT-{uuid4()}",
        phone_number=None
        # Los demás campos se pueden llenar posteriormente
    )
    
    db.add(company)
    db.flush()  # Para obtener el ID
    
    # Aquí podrías agregar lógica adicional de tenant:
    # - Crear schemas específicos si usas schema-per-tenant
    # - Configurar límites por defecto
    # - Crear PDVs por defecto
    # - Inicializar configuraciones base
    
    db.commit()
    db.refresh(company)
    
    return company


def update_company(db, company_update, current_user):
    """
    Update company information.
    NIT cannot be updated.
    """
    # Get user's active company
    user_company = db.query(UserCompany).join(Company).filter(
        UserCompany.user_id == current_user.id,
        UserCompany.is_active == True,
        UserCompany.role.in_(["admin", "owner"])
    ).first()
    
    if not user_company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes permisos para actualizar esta empresa"
        )

    company = user_company.company

    # Update only provided fields, excluding NIT
    if company_update.name is not None:
        # Check if name already exists (excluding current company)
        existing = db.query(Company).filter(
            Company.name == company_update.name,
            Company.id != company.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una empresa con este nombre"
            )
        company.name = company_update.name

    if company_update.description is not None:
        company.description = company_update.description
    if company_update.address is not None:
        company.address = company_update.address
    if company_update.phone_number is not None:
        company.phone_number = company_update.phone_number
    if company_update.economic_activity is not None:
        company.economic_activity = company_update.economic_activity
    if company_update.quantity_employees is not None:
        company.quantity_employees = company_update.quantity_employees
    if company_update.social_reason is not None:
        company.social_reason = company_update.social_reason

    db.commit()
    db.refresh(company)
    return company


def upload_company_logo(db, file, current_user):
    """
    Upload company logo to MinIO and update company.
    """
    from app.modules.files.service import upload_file_to_minio
    import uuid

    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos de imagen"
        )

    # Get user's active company
    user_company = db.query(UserCompany).join(Company).filter(
        UserCompany.user_id == current_user.id,
        UserCompany.is_active == True,
        UserCompany.role.in_(["admin", "owner"])
    ).first()
    
    if not user_company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes permisos para actualizar el logo de esta empresa"
        )

    company = user_company.company

    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    unique_filename = f"logo_{uuid.uuid4()}.{file_extension}"
    file_key = f"company-logos/{company.id}/{unique_filename}"

    try:
        # Upload to MinIO
        file_url = upload_file_to_minio(
            file=file,
            bucket_name="ally360",
            object_key=file_key
        )

        # Update company logo
        company.logo = file_url
        db.commit()

        return {
            "message": "Logo subido exitosamente",
            "logo_url": file_url
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir logo: {str(e)}"
        )


def get_company_logo_url(db, current_user):
    """
    Get presigned URL for company logo.
    """
    try:
        # Get current user's company
        user_company = db.query(UserCompany).filter(
            UserCompany.user_id == current_user.id
        ).first()

        if not user_company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no pertenece a ninguna empresa"
            )

        company = db.query(Company).filter(
            Company.id == user_company.company_id
        ).first()

        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada"
            )

        if not company.logo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La empresa no tiene logo"
            )

        # Extract MinIO key from stored URL
        logo_url = company.logo
        if "/ally360/" in logo_url:
            object_key = logo_url.split("/ally360/", 1)[1]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="URL de logo inválida"
            )

        from app.modules.files.service import get_presigned_download_url
        
        # Generate temporary URL valid for 1 hour
        presigned_url = get_presigned_download_url(
            bucket_name="ally360",
            object_key=object_key,
            expires_in_hours=1
        )

        return {
            "logo_url": presigned_url,
            "expires_in": "1 hour"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener logo: {str(e)}"
        )

