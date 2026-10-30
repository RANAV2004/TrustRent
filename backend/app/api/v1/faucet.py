from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.models.user import User
from app.api.v1.auth import get_current_user
router = APIRouter(prefix="/faucet", tags=["Testnet Faucet"])
class FaucetRequest(BaseModel):
    recipient_address: str
class FaucetResponse(BaseModel):
    success: bool
    amount_inr: float
    message: str
@router.post("/", response_model=FaucetResponse)  # faucet
async def request_faucet(
    request: FaucetRequest,
    current_user: User = Depends(get_current_user)
):
    if not request.recipient_address.startswith("0x") or len(request.recipient_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid EVM recipient address")
    return FaucetResponse(
        success=True,
        amount_inr=50000.0,
        message=f"Dispensed 50,000 MockINR to {request.recipient_address} on testnet"
    )
