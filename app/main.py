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

app = FastAPI(title="Nexus Council")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

@app.post("/api/council", response_model=SessionCreateResponse)
async def create_council(
    request: SessionCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    architect = ArchitectService()
    session = await architect.design_council(request.prompt, db)
    initiate_hunt.delay(str(session.id))
    return SessionCreateResponse(session_id=session.id, status="PROCESSING")

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