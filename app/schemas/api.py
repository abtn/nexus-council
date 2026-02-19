from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid

# --- ENUMS ---
class CouncilMode(str, Enum):
    STANDARD = "standard"      # 1 Prompt -> Parallel Personas
    DECOMPOSITION = "decomposition" # 1 Prompt -> Sub-queries -> Parallel Research
    QUICK = "quick"           # Direct LLM answer, no search

class ToneStyle(str, Enum):
    ACADEMIC = "academic"
    BUSINESS = "business"
    TECHNICAL = "technical"
    CASUAL = "casual"

class OutputLength(str, Enum):
    CONCISE = "concise"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"

# --- CONFIG MODELS ---
class ModelSelection(BaseModel):
    architect: str
    hunter: str   # Used for query generation
    analyst: str  # Used for reading/writing reports
    moderator: str # Used for final synthesis

class ExpertDefinition(BaseModel):
    name: str
    role_description: str
    initial_search_queries: List[str]
    brain_tier: str = "economy"

class ArchitectDecision(BaseModel):
    experts: List[ExpertDefinition] = Field(..., min_length=1, max_length=10)

# --- REQUEST/RESPONSE ---
class SessionCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=5)
    mode: CouncilMode = CouncilMode.STANDARD
    models: Optional[ModelSelection] = None
    tone: ToneStyle = ToneStyle.ACADEMIC
    length: OutputLength = OutputLength.STANDARD
    enable_search: bool = True
    decomposition_depth: int = Field(3, ge=2, le=5)

class SessionCreateResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    mode: CouncilMode

class AgentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    role_description: str
    status: str

class SessionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_prompt: str
    status: str
    mode: str  # Added field
    consensus: Optional[str]
    friction: Optional[str]
    recommendation: Optional[str]
    created_at: datetime
    agents: List[AgentStatusResponse] = []