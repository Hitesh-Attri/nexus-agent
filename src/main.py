"""nexus-agent FastAPI app.

Stateless by design: no model, no database, no warm-up. Reasoning goes to the
gateway and retrieval to nexus-rag, both over HTTP.
"""

from __future__ import annotations

from fastapi import FastAPI

from api.agent import router as agent_router
from api.health import router as health_router

app = FastAPI(title="nexus-agent", version="0.1.0")
app.include_router(health_router)
app.include_router(agent_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8082, reload=True)