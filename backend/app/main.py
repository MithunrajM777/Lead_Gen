from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import models, database
from .database import engine
from .routes import auth, leads, admin
import os
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create tables
database.ensure_legacy_schema_compatibility()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Website Scraping & Lead Generation Tool")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(leads.router, tags=["Leads & Scraping"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/")
async def root():
    return {"message": "LeadGen API is running", "version": "2.0.0"}
