from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.api.auth import router as auth_router
from apps.api.app.core.database import engine
from apps.api.app.models.user import Base

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
