from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mangum import Mangum
from dotenv import load_dotenv
import os

load_dotenv()

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

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Register routers
from .routers import pages, accounts, contributions, loans, reports

app.include_router(pages.router)
app.include_router(accounts.router)
app.include_router(contributions.router)
app.include_router(loans.router)
app.include_router(reports.router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "shaker-fonafahe", "version": "2.0.0"}


# Vercel serverless handler
handler = Mangum(app)
