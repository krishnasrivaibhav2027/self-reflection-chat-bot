from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    first_name: str = Field(..., min_length = 3, max_length = 30)
    last_name: str = Field(..., min_length = 3, max_length = 30)
    email: EmailStr
    password: str = Field(..., min_length = 8, max_length=20)
    confirm_password: str = Field(..., min_length= 8, max_length=20)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c in "!@#$%^&*" for c in v):
            raise ValueError("Password must contain at least one special character.")
        return v
    
    @model_validator(mode='after')
    def validate_confirm_password(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    login_at: datetime
    logout_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes = True)
