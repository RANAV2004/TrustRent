from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from decimal import Decimal
from app.models.tenancy import TenancyStateEnum
class DraftTenancyRequest(BaseModel):
    tenant_email: str
    property_address: str
    monthly_rent: Decimal = Field(gt=0)
    deposit_amount: Decimal = Field(gt=0)
    deduction_cap: Decimal = Field(gt=0)
    claim_window_days: int = Field(default=7, ge=3, le=30)
class DraftTenancyResponse(BaseModel):
    tenancy_id: str
    lease_hash: str
    storage_cid: str
    deposit_amount: Decimal
    deduction_cap: Decimal
    claim_window_seconds: int
    contract_deploy_params: dict
class TenancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    vault_address: Optional[str] = None
    landlord_id: str
    tenant_id: str
    property_address: str
    monthly_rent: Decimal
    deposit_amount: Decimal
    deduction_cap: Decimal
    claim_window_days: int
    lease_hash: str
    state: TenancyStateEnum
