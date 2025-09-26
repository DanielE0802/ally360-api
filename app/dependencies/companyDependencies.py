from typing import Annotated
from fastapi import Depends
from app.modules.company.utils import get_current_user_and_company

UserCompanyContext = Annotated[dict, Depends(get_current_user_and_company)]
