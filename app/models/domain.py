import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base

class CouncilSession(Base):
    __tablename__ = "council_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")

    # --- NEW CONFIGURATION COLUMNS ---
    mode: Mapped[str] = mapped_column(String(20), default="standard")
    tone: Mapped[str] = mapped_column(String(20), default="academic")
    output_length: Mapped[str] = mapped_column(String(20), default="standard")
    enable_search: Mapped[bool] = mapped_column(Boolean, default=True)
    # OPTIMIZATION: Changed JSON to JSONB for binary storage and indexing capabilities
    model_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # ---------------------------------

    consensus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    friction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # OPTIMIZATION: Moved timestamp logic to the Database server
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agents: Mapped[List["AgentPersona"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class AgentPersona(Base):
    __tablename__ = "agent_personas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("council_sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_description: Mapped[str] = mapped_column(Text, nullable=False)
    brain_tier: Mapped[str] = mapped_column(String(20), default="economy")
    search_queries: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    
    # OPTIMIZATION: Moved timestamp logic to the Database server
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    session: Mapped["CouncilSession"] = relationship(back_populates="agents")
    knowledge_items: Mapped[List["KnowledgeItem"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    report: Mapped[Optional["ExpertReport"]] = relationship(back_populates="agent", uselist=False, cascade="all, delete-orphan")

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_personas.id", ondelete="CASCADE"))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # OPTIMIZATION: Changed JSON to JSONB
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384), nullable=True)
    
    # OPTIMIZATION: Moved timestamp logic to the Database server
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    agent: Mapped["AgentPersona"] = relationship(back_populates="knowledge_items")

class ExpertReport(Base):
    __tablename__ = "expert_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_personas.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # OPTIMIZATION: Moved timestamp logic to the Database server
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    agent: Mapped["AgentPersona"] = relationship(back_populates="report")