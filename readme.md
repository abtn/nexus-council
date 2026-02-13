
# Nexus Council

We are creating an autonomous "Council of Experts" system designed to solve complex problems by mimicking a structured debate and research process.

The system utilizes a multi-agent architecture where an **Architect** designs a team of specialized AI agents (Experts). These experts then **Hunt** for information using real-time web search, **Analyze** the findings, and a **Moderator** synthesizes their discoveries into a comprehensive, citable report.

### Current Status
- **Phase 1 (Architect):** Complete. The system dynamically creates specialized agents based on the user's prompt.
- **Phase 2 (Hunter):** Complete. Agents perform autonomous web research using Tavily and store knowledge in a vector-ready database.

### Optimal Result
The end goal is a fully interactive **Dashboard for the Council of Nexus**. Users will be able to:
1.  Submit complex queries.
2.  Watch in real-time as AI experts are assembled.
3.  Track the live research progress of each agent.
4.  View the final synthesized consensus, friction points, and detailed citations in a clean, well-designed interface.

### Tech Stack
- **Backend:** FastAPI, Celery, Redis
- **Database:** PostgreSQL (with `pgvector`)
- **AI:** Multi-Provider LLM Support (AvalAI, OpenRouter, Cloudflare)
- **Tools:** Tavily (Search), Trafilatura (Scraping)
