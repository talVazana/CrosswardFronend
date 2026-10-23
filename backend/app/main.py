from fastapi import FastAPI

from .api.routes.admin import router as admin_router
from .api.routes.drafts import router as drafts_router
from .api.routes.gameplay import router as gameplay_router
from .api.routes.rooms import router as rooms_router
from .api.routes.submissions import router as submissions_router

app = FastAPI()

app.include_router(rooms_router)
app.include_router(drafts_router)
app.include_router(admin_router)
app.include_router(submissions_router)
app.include_router(gameplay_router)


@app.get("/health")
def health():
    return {"status": "ok"}
