from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import auth, chat, dashboard, exports, faculty, labs, marks, notices, notifications, users

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Department Smart Portal", version="1.0.0")

# The Vite dev server runs on :5173 during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
for module in (marks, labs, faculty, notices, exports, notifications, chat, dashboard):
    app.include_router(module.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built React app (frontend/dist) from the same server, so one command runs everything.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = DIST / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
