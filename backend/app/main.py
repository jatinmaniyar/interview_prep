from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import problems, runner

app = FastAPI(title="Interview Prep API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(problems.router, prefix="/api")
app.include_router(runner.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
