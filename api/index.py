import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # Vercel: env from platform. Local dev: pip install python-dotenv for .env files.
    pass

app = FastAPI(
    title="Shaker - FONAFAHE",
    description="Collaborative Funding Financial Movements System",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def locale_middleware(request: Request, call_next):
    lang = request.cookies.get("lang", "en")
    if lang not in ("en", "es"):
        lang = "en"
    request.state.locale = lang
    return await call_next(request)


# Mount static files (only works locally; Vercel serves static via routes config)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    path = os.path.join(static_dir, "favicon.ico")
    if os.path.isfile(path):
        return FileResponse(path, media_type="image/x-icon")
    raise HTTPException(status_code=404)


if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Register routers
from .routers import accounts, contributions, loans, pages, profile, reports, users

app.include_router(pages.router)
app.include_router(accounts.router)
app.include_router(contributions.router)
app.include_router(loans.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(profile.router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "shaker-fonafahe", "version": "2.0.0"}
