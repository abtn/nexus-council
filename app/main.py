from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.orm import selectinload
from arq import create_pool
from arq.connections import RedisSettings

from app.core.database import get_db, engine, Base
from app.core.config import get_settings
from app.schemas.api import SessionCreateRequest, SessionCreateResponse, SessionDetailResponse
from app.models.domain import CouncilSession
from app.services.architect_service import ArchitectService
import uuid

app = FastAPI(title="Nexus Council v2")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

@app.post("/api/council", response_model=SessionCreateResponse)
async def create_council(request: SessionCreateRequest, db: AsyncSession = Depends(get_db)):
    
    # 1. Create Session Record with Config
    session = CouncilSession(
        user_prompt=request.prompt,
        mode=request.mode,
        tone=request.tone,
        output_length=request.length,
        enable_search=request.enable_search,
        model_config=request.models.dict() if request.models else None,
        status="PROCESSING"
    )
    db.add(session)
    await db.flush() 

    # 2. Architect Strategy (Handles Standard vs Decomposition)
    architect = ArchitectService()
    await architect.blueprint_session(session, request.decomposition_depth, db)

    # Commit changes to DB
    await db.commit()

    # 3. Trigger Workers (ARQ implementation)
    
    # Create Redis connection
    redis = await create_pool(RedisSettings.from_dsn(get_settings().REDIS_URL))
    
    # CRITICAL FIX: Re-fetch session using selectinload to ensure agents are loaded
    # We cannot rely on lazy loading in async code.
    result = await db.execute(
        select(CouncilSession)
        .where(CouncilSession.id == session.id)
        .options(selectinload(CouncilSession.agents)) # <--- Forces loading of agents immediately
    )
    session = result.scalars().first()
    
    if not session:
        await redis.close()
        raise HTTPException(status_code=404, detail="Session lost after creation")

    # Now we can safely iterate agents without triggering a lazy load error
    model_config = session.model_config

    for agent in session.agents:
        await redis.enqueue_job(
            'execute_expert_search',
            str(agent.id),
            agent.search_queries or [],
            session.enable_search,
            model_config
        )
    
    await redis.close()

    return SessionCreateResponse(
        session_id=session.id, 
        status="PROCESSING",
        mode=session.mode
    )

@app.get("/api/council/{session_id}", response_model=SessionDetailResponse)
async def get_council(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CouncilSession)
        .where(CouncilSession.id == session_id)
        .options(selectinload(CouncilSession.agents))
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session