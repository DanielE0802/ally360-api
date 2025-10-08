from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.modules.company.schemas import CompanyCreate, CompanyOutWithRole, AssignUserToCompany
from app.modules.auth.utils import create_access_token
from app.dependencies.dbDependecies import db_dependency
from app.modules.auth.models import User, UserCompany
from app.modules.company.models import Company
from uuid import UUID

def create_company(db: db_dependency, company_data: CompanyCreate, current_user: User) -> dict:
    """
    Create a new company in the database.
    Optionally creates a main PDV if uniquePDV is True.

    Args:
        company_data (CompanyCreate): The company data to create.
        current_user (User): The current user creating the company.

    Returns:
        dict: The created company object with additional info.
    """

    if db.query(Company).filter_by(name=company_data.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name already exists")

    # Extract uniquePDV flag before creating company
    unique_pdv = company_data.uniquePDV
    company_dict = company_data.model_dump()
    del company_dict['uniquePDV']  # Remove from company data as it's not a company field

    company = Company(**company_dict)
    db.add(company)
    db.flush()

    user_company = UserCompany(user_id=current_user.id, company_id=company.id, is_active=True, role="admin")
    db.add(user_company)
    
    main_pdv_created = False
    
    # If uniquePDV is True, create a main PDV with company information
    if unique_pdv:
        from app.modules.pdv.models import PDV
        
        main_pdv = PDV(
            tenant_id=company.id,  # Company ID acts as tenant_id
            name="Principal",  # Default name for main PDV
            address=company.address or "Dirección principal",
            phone_number=company.phone_number,
            is_main=True,
            is_active=True
        )
        db.add(main_pdv)
        main_pdv_created = True
        
        # Initialize stock for this PDV if needed
        try:
            from app.modules.inventory.service import InventoryService
            inventory_service = InventoryService(db)
            db.flush()  # Ensure PDV has an ID
            inventory_service.create_stock_for_new_pdv(str(company.id), main_pdv.id)
        except Exception as e:
            # If inventory service fails, log but don't fail company creation
            print(f"Warning: Could not initialize stock for main PDV: {e}")

    db.commit()
    db.refresh(company)

    # Prepare response with company data and additional info
    company_dict = {
        **company_data.model_dump(),
        "id": company.id,
        "main_pdv_created": main_pdv_created
    }

    return company_dict

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


def update_company_by_id(db, company_id: UUID, company_update, current_user):
    """
    Update company information by ID with ownership validation.
    Only users with owner or admin role can update company data.
    NIT cannot be updated.
    """
    # Verify user has access to this company
    user_company = db.query(UserCompany).join(Company).filter(
        UserCompany.user_id == current_user.id,
        UserCompany.company_id == company_id,
        UserCompany.is_active == True,
        UserCompany.role.in_(["admin", "owner"])
    ).first()
    
    if not user_company:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar esta empresa o la empresa no existe"
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


def get_company_me_detail(db: Session, current_user: User) -> dict:
    """
    Obtener información completa de la empresa del usuario actual.
    Incluye PDVs con información de ubicación y URL segura para el logo.
    
    Args:
        db (Session): Sesión de base de datos
        current_user (User): Usuario actual autenticado
        
    Returns:
        dict: Información completa de la empresa con PDVs y ubicaciones
    """
    from app.modules.files.service import get_presigned_download_url
    
    try:
        # Obtener la empresa actual del usuario con la relación UserCompany
        user_company = db.query(UserCompany).filter(
            UserCompany.user_id == current_user.id,
            UserCompany.is_active == True
        ).first()
        
        if not user_company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no pertenece a ninguna empresa activa"
            )
        
        # Obtener la empresa con todos los PDVs y sus ubicaciones
        company = db.query(Company).filter(
            Company.id == user_company.company_id
        ).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada"
            )
        
        # Obtener PDVs con ubicaciones usando joins explícitos
        from app.modules.pdv.models import PDV
        from app.modules.locations.models import Department, City
        
        pdvs_query = db.query(PDV).options(
            joinedload(PDV.department),
            joinedload(PDV.city)
        ).filter(
            PDV.tenant_id == company.id
        ).all()
        
        # Generar URL segura para el logo si existe
        logo_url = None
        if company.logo:
            try:
                logo_url = get_presigned_download_url(
                    bucket_name="ally360",
                    object_key=company.logo,
                    expires_in_hours=24  # URL válida por 24 horas
                )
            except Exception as e:
                # Si falla la generación de URL, continúa sin logo_url
                print(f"Warning: No se pudo generar URL para logo: {e}")
        
        # Preparar datos de PDVs con ubicaciones
        pdvs_data = []
        for pdv in pdvs_query:
            pdv_data = {
                "id": pdv.id,
                "name": pdv.name,
                "address": pdv.address,
                "phone_number": pdv.phone_number,
                "is_main": pdv.is_main,
                "is_active": pdv.is_active,
                "created_at": pdv.created_at,
                "updated_at": pdv.updated_at,
                "department_id": pdv.department_id,
                "city_id": pdv.city_id,
                "department": None,
                "city": None
            }
            
            # Agregar información del departamento si existe
            if pdv.department:
                pdv_data["department"] = {
                    "id": pdv.department.id,
                    "name": pdv.department.name,
                    "code": pdv.department.code
                }
            
            # Agregar información de la ciudad si existe
            if pdv.city:
                pdv_data["city"] = {
                    "id": pdv.city.id,
                    "name": pdv.city.name,
                    "code": pdv.city.code,
                    "department_id": pdv.city.department_id
                }
            
            pdvs_data.append(pdv_data)
        
        # Preparar respuesta completa
        company_detail = {
            "id": company.id,
            "name": company.name,
            "description": company.description,
            "address": company.address,
            "phone_number": company.phone_number,
            "nit": company.nit,
            "economic_activity": company.economic_activity,
            "quantity_employees": company.quantity_employees,
            "social_reason": company.social_reason,
            "logo": company.logo,  # Clave interna del archivo
            "logo_url": logo_url,  # URL segura temporal
            "is_active": company.is_active,
            "created_at": company.created_at,
            "user_role": user_company.role,
            "pdvs": pdvs_data
        }
        
        return company_detail
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener información de la empresa: {str(e)}"
        )

