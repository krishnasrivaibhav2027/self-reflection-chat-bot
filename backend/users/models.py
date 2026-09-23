from sqlalchemy import Integer, String, func
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime
from typing import Optional
from backend.core.database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key = True)
    first_name: Mapped[str] = mapped_column(String(20), nullable = False)
    last_name: Mapped[str] = mapped_column(String(30), nullable = False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable = False)
    login_at: Mapped[datetime] = mapped_column(server_default = func.now(), nullable = False)
    logout_at: Mapped[Optional[datetime]] = mapped_column(nullable = True)