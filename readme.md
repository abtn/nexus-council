
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

### Features
- **Parallel Research:** Multiple agents hunt for data simultaneously.
- **Provider Agnostic:** Supports AvalAI, Cloudflare (Llama), and OpenRouter.
- **RAG-Ready:** Knowledge is stored in a structured PostgreSQL database with `pgvector` support.
- **Truth Discovery:** The Moderator identifies points of "Friction" where experts or sources disagree.

### Tech Stack
- **Backend:** FastAPI, Celery (Task Queue), Redis (Broker/Backend)
- **Database:** PostgreSQL + `pgvector`
- **AI Models (Dev):** Gemini 2.0 Flash Lite (AvalAI), Llama 3.1 8b (Cloudflare)
- **Search & Scraping:** Tavily API & Trafilatura

### Recent Example Result
**Prompt:** *"What is the PI number"*
- **Consensus:** Pi (π) is the ratio of a circle's circumference to its diameter (~3.14159).
- **Friction:** Identified that while the Euclidean definition is standard, it varies in non-Euclidean (curved) spaces.
- **Status:** `COMPLETED`