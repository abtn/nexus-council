from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.orm import selectinload
from app.core.database import get_db, engine, Base
from app.schemas.api import SessionCreateRequest, SessionCreateResponse, SessionDetailResponse
from app.models.domain import CouncilSession
from app.services.architect_service import ArchitectService
from app.workers.tasks import initiate_hunt
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

    await db.commit()
    await db.refresh(session)

    # 3. Trigger Workers
    initiate_hunt.delay(str(session.id)) # pyright: ignore[reportFunctionMemberAccess]

    return SessionCreateResponse(
        session_id=session.id, 
        status="PROCESSING",
        mode=session.mode # pyright: ignore[reportArgumentType]
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