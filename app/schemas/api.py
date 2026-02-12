from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class ExpertDefinition(BaseModel):
    name: str
    role_description: str
    initial_search_queries: List[str]
    brain_tier: str = "economy" # Changed from model_tier

class ArchitectDecision(BaseModel):
    experts: List[ExpertDefinition] = Field(..., min_length=3, max_length=5)

class SessionCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=10)

class SessionCreateResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    message: str = "Council assembly initiated."

class SessionDetailResponse(BaseModel):
    id: uuid.UUID
    user_prompt: str
    status: str
    consensus: Optional[str]
    friction: Optional[str]
    recommendation: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True