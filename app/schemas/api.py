from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
import uuid

class ExpertDefinition(BaseModel):
    name: str
    role_description: str
    initial_search_queries: List[str]
    brain_tier: str = "economy"

class ArchitectDecision(BaseModel):
    experts: List[ExpertDefinition] = Field(..., min_length=3, max_length=5)

class SessionCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=10)

class SessionCreateResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    message: str = "Council assembly initiated."

# --- NEW SCHEMA ---
class AgentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True) # Pydantic V2 syntax
    
    id: uuid.UUID
    name: str
    role_description: str
    status: str

class SessionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True) # Pydantic V2 syntax
    
    id: uuid.UUID
    user_prompt: str
    status: str
    consensus: Optional[str]
    friction: Optional[str]
    recommendation: Optional[str]
    created_at: datetime
    agents: List[AgentStatusResponse] = []