from typing import Annotated
from fastapi import Depends
from app.modules.auth.utils import get_current_user
from app.modules.auth.models import User

user_dependency = Annotated[User, Depends(get_current_user)]
