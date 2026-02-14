from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
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
        # 1. Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # 2. Create tables
        await conn.run_sync(Base.metadata.create_all)

@app.post("/api/council", response_model=SessionCreateResponse)
async def create_council(
    request: SessionCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    # 1. Architect Phase (Synchronous)
    architect = ArchitectService()
    session = await architect.design_council(request.prompt, db)

    # 2. Hunter Phase (Asynchronous Trigger)
    initiate_hunt.delay(str(session.id))

    return SessionCreateResponse(
        session_id=session.id,
        status="PROCESSING"
    )

@app.get("/api/council/{session_id}", response_model=SessionDetailResponse)
async def get_council(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Retrieves the status and final results of a Council Session.
    """
    result = await db.execute(select(CouncilSession).where(CouncilSession.id == session_id))
    session = result.scalars().first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session