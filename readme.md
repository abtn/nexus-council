
# Nexus Council

Nexus Council is an autonomous "Council of Experts" system designed to solve complex problems by mimicking a structured human research and debate process. 

The system utilizes a multi-agent architecture where an **Architect** designs a team of specialized AI agents. These experts then **Hunt** for information via real-time web search, **Analyze** their findings into individual reports, and a **Moderator** synthesizes these discoveries into a final, actionable consensus.

### Current Status
- **Phase 1 (Architect): ✅ Complete.** Dynamically creates specialized agents based on user prompts.
- **Phase 2 (Hunter): ✅ Complete.** Agents perform autonomous web research and document scraping.
- **Phase 3 (Analyst & Moderator): ✅ Complete.** 
    - **Analysis:** Agents read gathered research and write citable reports.
    - **Synthesis:** A Moderator aggregates all expert reports into a final Consensus, Friction point analysis, and Recommendation.
    - **Orchestration:** Implemented using Celery Chords to ensure parallel processing and synchronized synthesis.
- **Phase 4 (RAG & Local Embeddings): ✅ Complete.** 
    - Integrated `pgvector` for similarity-based research analysis.
    - Implemented local embedding generation via `sentence-transformers` (all-MiniLM-L6-v2).
    - Refined citation logic to preserve source URLs across fragmented research data.
- **Phase 5 (Interactive Dashboard): ✅ Complete.**
    - Developed a real-time Streamlit dashboard to visualize agent progress and final reports.
    - Containerized the entire ecosystem (API, Worker, Dashboard, DB, Cache).

### Core Features
- **Local RAG:** Agents use vector search to find the most relevant context for their reports, making it cost-efficient and scalable.
- **Centralized Model Registry:** Managed in `config.py` for rapid switching between provider tiers (AvalAI, Cloudflare, OpenRouter).
- **Parallel Workflows:** Celery Chords ensure parallel agent execution with a synchronized moderation step.
- **Modern Tech Stack:** Pydantic V2, SQLAlchemy 2.0 (Async), pgvector, and FastAPI.

### Infrastructure
- **Orchestration:** Docker Compose
- **Database:** PostgreSQL + pgvector
- **Task Queue:** Celery + Redis
- **Embedding Engine:** Torch / Sentence-Transformers (Local CPU)

### Example Result
**Prompt:** *"What is the PI number"*
- **Consensus:** Pi (π) is the ratio of a circle's circumference to its diameter (~3.14159).
- **Friction:** Identified that while the Euclidean definition is standard, it varies in non-Euclidean (curved) spaces.
- **Status:** `COMPLETED`