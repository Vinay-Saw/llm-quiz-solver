"""
FastAPI server for handling quiz requests
Refactored for Render.com deployment with Lifecycle management and Task tracking
"""
import asyncio
import os
import logging
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright

from quiz_solver import QuizSolver, set_global_browser, close_global_browser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL", "")
STUDENT_SECRET = os.getenv("STUDENT_SECRET", "")

# Store strong references to background tasks to prevent Garbage Collection
background_tasks: Set[asyncio.Task] = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    Initializes Playwright browser on startup and cleans up on shutdown.
    """
    logger.info("Starting up: Initializing Playwright Browser...")
    playwright = await async_playwright().start()
    # Launch browser once. Re-use contexts for requests.
    # Args help with containerized environments (Render/Docker)
    browser = await playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
    )
    set_global_browser(browser)
    
    yield
    
    logger.info("Shutting down: Closing Browser...")
    await close_global_browser()
    await playwright.stop()

app = FastAPI(title="LLM Quiz Solver API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

class QuizResponse(BaseModel):
    status: str
    message: str

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "LLM Quiz Solver",
        "version": "2.0.0"
    }

@app.post("/quiz", response_model=QuizResponse)
async def handle_quiz(request: QuizRequest):
    """
    Main endpoint to receive quiz requests
    Returns immediately with 200, then processes quiz in background
    """
    try:
        # Validate secret
        if request.secret != STUDENT_SECRET:
            logger.warning(f"Invalid secret from {request.email}")
            raise HTTPException(status_code=403, detail="Invalid secret")
        
        # Validate email
        if request.email != STUDENT_EMAIL:
            logger.warning(f"Invalid email: {request.email}")
            raise HTTPException(status_code=403, detail="Invalid email")
        
        logger.info(f"Received quiz request for URL: {request.url}")
        
        # Create background task with reference tracking
        task = asyncio.create_task(solve_quiz_wrapper(request))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        
        return QuizResponse(
            status="accepted",
            message="Quiz processing started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling quiz request: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Bad request: {str(e)}")

async def solve_quiz_wrapper(request: QuizRequest):
    """
    Wrapper to catch exceptions in background tasks
    """
    try:
        solver = QuizSolver(
            email=request.email,
            secret=request.secret
        )
        await solver.solve_quiz_chain(request.url)
    except Exception as e:
        logger.error(f"Critical error in background task: {str(e)}", exc_info=True)

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "email_configured": bool(STUDENT_EMAIL),
        "secret_configured": bool(STUDENT_SECRET),
        "active_tasks": len(background_tasks)
    }

if __name__ == "__main__":
    import uvicorn
    # Note: In production, the browser launch inside lifespan will handle initialization
    uvicorn.run(app, host="0.0.0.0", port=8000)
