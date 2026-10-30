from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from app.models.user import UserRole
class UserLoginRequest(BaseModel):
    email: EmailStr
    name: str
    role: UserRole
    smart_account_address: Optional[str] = None
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    name: str
    role: UserRole
    wallet_address: Optional[str] = None
    is_verified: bool
    attestation_hash: Optional[str] = None
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
class MockVerifyRequest(BaseModel):
    full_name: str
    id_type: str
    id_number: str
    phone: str
class VerificationResult(BaseModel):
    verified: bool
    attestation_hash: str
    transaction_hash: Optional[str] = None
    message: str
