from fastapi import APIRouter, HTTPException, status
from app.modules.auth.schemas import UserCreate, TokenResponse
from app.modules.auth.utils import hash_password, verify_password, create_access_token, verify_token
from app.dependencies.dbDependecies import db_dependency
from app.modules.auth.models import User, Profile, UserCompany
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

