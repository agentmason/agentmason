from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.api.auth import router as auth_router
from apps.api.app.api.agents import router as agents_router
from apps.api.app.api.me import router as me_router
from apps.api.app.api.organizations import router as organizations_router
from apps.api.app.api.knowledge import router as knowledge_router
from apps.api.app.api.integrations import router as integrations_router
from apps.api.app.core.database import engine
from apps.api.app.models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgentMason API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(me_router, prefix="/me", tags=["me"])
app.include_router(organizations_router, prefix="/organizations", tags=["organizations"])
app.include_router(agents_router, prefix="/agents", tags=["agents"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(integrations_router, prefix="/api/integrations", tags=["integrations"])
