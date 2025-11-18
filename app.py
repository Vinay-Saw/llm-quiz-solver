"""
FastAPI server for handling quiz requests
"""
import asyncio
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from quiz_solver import QuizSolver

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Quiz Solver API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL", "")
STUDENT_SECRET = os.getenv("STUDENT_SECRET", "")

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
        "version": "1.0.0"
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
        
        # Start quiz solving in background (non-blocking)
        asyncio.create_task(solve_quiz_async(request))
        
        # Return immediately
        return QuizResponse(
            status="accepted",
            message="Quiz processing started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling quiz request: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Bad request: {str(e)}")

async def solve_quiz_async(request: QuizRequest):
    """
    Asynchronously solve the quiz
    This runs in the background after returning 200 to the caller
    """
    try:
        solver = QuizSolver(
            email=request.email,
            secret=request.secret
        )
        
        # Solve the quiz (this may chain through multiple URLs)
        await solver.solve_quiz_chain(request.url)
        
    except Exception as e:
        logger.error(f"Error solving quiz: {str(e)}", exc_info=True)

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "email_configured": bool(STUDENT_EMAIL),
        "secret_configured": bool(STUDENT_SECRET),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
