from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from app.database.database import get_db, get_async_db

# Synchronous database dependency (for migrations and legacy code)
db_dependency = Annotated[Session, Depends(get_db)]

# Asynchronous database dependency (preferred for new endpoints)
async_db_dependency = Annotated[AsyncSession, Depends(get_async_db)]
