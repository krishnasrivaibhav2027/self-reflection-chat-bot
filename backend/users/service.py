from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from typing import Optional

from sqlalchemy.exc import IntegrityError
from backend.core.database import get_db
from backend.users.repository import UserRepository
from backend.users.schemas import UserCreate
from backend.users.models import User
from backend.core.security import hash_password

class UserService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repository = UserRepository(db)
    
    async def create_user(self, user_create: UserCreate) -> User:
        existing_user = await self.repository.get_user_by_email(user_create.email)
        if existing_user:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "A user with this email already exists"
            )
        
        hashed_password = hash_password(user_create.password)
        db_user = User(
            first_name = user_create.first_name,
            last_name = user_create.last_name,
            email = user_create.email,
            hashed_password = hashed_password,
        )

        try:
            return await self.repository.create_user(db_user)
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code = status.HTTP_400_BAD_REQUEST, detail = "A user with this email already exists")
        
    async def get_user_by_email(self, email: str) -> Optional[User]:
        return await self.repository.get_user_by_email(email)
    
