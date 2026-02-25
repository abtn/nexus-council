from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings
import logging

# 1. EXPLICIT IMPORTS
# We import the tasks module directly so we can pass the function objects to ARQ.
from app.workers import tasks 

logger = logging.getLogger(__name__)
settings = get_settings()

async def startup(ctx):
    logger.info("ARQ Worker Started")

async def shutdown(ctx):
    logger.info("ARQ Worker Shutting Down")

class WorkerSettings:
    """
    Configuration for the ARQ worker.
    """
    # 2. PASS FUNCTION OBJECTS DIRECTLY
    # This guarantees ARQ knows exactly which function maps to which name.
    functions = [
        tasks.execute_expert_search,
        tasks.synthesize_council,
        tasks.finalize_quick_session
    ]
    
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    
    on_startup = startup
    on_shutdown = shutdown
    
    # Handle bursts of agent creation
    max_jobs = 10 