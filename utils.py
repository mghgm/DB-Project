from pydantic import BaseModel

class ChargeRequest(BaseModel):
    user_id: int
    amount: float

class ChargeResponse(BaseModel):
    url: str
    token: str
    trx_id: int

class ChargeAckRequest(BaseModel):
    token: str
    trx_id: int
    user_id: str

class ChargeAckResponse(BaseModel):
    status: str = "verified"
