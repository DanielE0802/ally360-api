from typing import Annotated
from fastapi import Depends
from app.modules.auth.utils import get_current_user

user_dependency = Depends(get_current_user)
