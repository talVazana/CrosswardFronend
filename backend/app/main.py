import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes.admin import router as admin_router
from .api.routes.admin_puzzles import router as admin_puzzles_router
from .api.routes.drafts import router as drafts_router
from .api.routes.e2e import router as e2e_router
from .api.routes.events import router as events_router
from .api.routes.gameplay import router as gameplay_router
from .api.routes.players import router as players_router
from .api.routes.rooms import router as rooms_router
from .api.routes.scores import router as scores_router
from .api.routes.submissions import router as submissions_router
from .services.firestore_loader import restore_state


@asynccontextmanager
async def lifespan(_app: FastAPI):
    restore_state()
    yield


app = FastAPI(lifespan=lifespan)

_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = [
    origin.strip() for origin in _origins_env.split(",") if origin.strip()
] or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5002",
    "http://127.0.0.1:5002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms_router)
app.include_router(players_router)
app.include_router(drafts_router)
app.include_router(admin_router)
app.include_router(admin_puzzles_router)
app.include_router(submissions_router)
app.include_router(scores_router)
app.include_router(gameplay_router)
app.include_router(events_router)
app.include_router(e2e_router)


@app.get("/health")
def health():
    return {"status": "ok"}
