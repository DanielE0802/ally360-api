from fastapi import APIRouter, HTTPException, status
from app.modules.auth.schemas import UserCreate, CompanyCreate, CompanyOutWithRole, TokenResponse, AssignUserToCompany
from app.modules.auth.utils import hash_password, verify_password, create_access_token, verify_token
from app.dependencies.dbDependecies import db_dependency
from app.modules.auth.models import User, Profile, UserCompany
from app.modules.auth.models import Company
from uuid import UUID

def create_user(db: db_dependency, user_data: UserCreate) -> User:
    """
    Create a new user in the database.

    Args:
        user_data (UserCreate): The user data to create.

    Returns:
        User: The created user object.
    """

    if db.query(User).filter_by(email=user_data.email).first():
        raise HTTPException(status_code=400, detail="Email ya registrado")

    profile = Profile(**user_data.profile.model_dump())
    db.add(profile)
    db.flush()

    hashed_password = hash_password(user_data.password)

    user = User(
        email=user_data.email,
        password=hashed_password,
        profile_id=profile.id
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def login_user(db: db_dependency, email: str, password: str) -> TokenResponse:
    """
    Authenticate a user by email and password.

    Args:
        email (str): The user's email.
        password (str): The user's password.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: If the user is not found or the password is incorrect.
    """

    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(password, user.password if isinstance(user.password, str) else user.password.value):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    if user.is_active is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    access_token = create_access_token(data={"email": user.email, "user_name": user.profile.first_name, "role": user.profile.role, "sub": str(user.id)})

    return TokenResponse(access_token=access_token, token_type="bearer")


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