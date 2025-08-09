"""FastAPI web interface for newsletter bot monitoring and control."""

import asyncio
import logging
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
import uvicorn

from src.models.settings import Settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Newsletter Automation Bot",
    description="Web interface for monitoring and controlling newsletter generation",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Global state for tracking running tasks
running_tasks = {}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    try:
        settings = Settings()
        
        # Get system status
        api_keys_status = {
            'readwise': bool(settings.readwise_api_key),
            'glasp': bool(settings.glasp_api_key),
            'buttondown': bool(settings.buttondown_api_key),
            'openrouter': bool(settings.openrouter_api_key),
            'unsplash': bool(settings.unsplash_api_key),
        }
        
        rss_count = len(settings.rss_feeds.split(',')) if settings.rss_feeds else 0
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "api_keys_status": api_keys_status,
            "rss_count": rss_count,
            "debug_mode": settings.debug,
            "infisical_enabled": settings.use_infisical,
            "running_tasks": len(running_tasks)
        })
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    try:
        settings = Settings()
        
        # Check critical API keys
        critical_keys = ['readwise_api_key', 'buttondown_api_key', 'openrouter_api_key']
        missing_critical = [key for key in critical_keys if not getattr(settings, key)]
        
        status = "healthy" if not missing_critical else "degraded"
        
        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "api_keys": {
                "readwise": bool(settings.readwise_api_key),
                "glasp": bool(settings.glasp_api_key), 
                "buttondown": bool(settings.buttondown_api_key),
                "openrouter": bool(settings.openrouter_api_key),
                "unsplash": bool(settings.unsplash_api_key),
            },
            "rss_feeds": len(settings.rss_feeds.split(',')) if settings.rss_feeds else 0,
            "missing_critical": missing_critical,
            "running_tasks": len(running_tasks)
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@app.post("/api/generate")
async def trigger_generation(background_tasks: BackgroundTasks, dry_run: bool = False):
    """Trigger newsletter generation."""
    task_id = f"generate-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    
    if len(running_tasks) >= 2:  # Limit concurrent tasks
        raise HTTPException(status_code=429, detail="Too many tasks running")
    
    running_tasks[task_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run
    }
    
    background_tasks.add_task(_run_newsletter_generation, task_id, dry_run)
    
    return {
        "task_id": task_id,
        "status": "started",
        "dry_run": dry_run,
        "message": "Newsletter generation started"
    }


@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific task."""
    if task_id not in running_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return running_tasks[task_id]


@app.get("/api/tasks")
async def list_tasks():
    """List all tasks."""
    return {
        "tasks": running_tasks,
        "total": len(running_tasks)
    }


async def _run_newsletter_generation(task_id: str, dry_run: bool):
    """Background task to run newsletter generation."""
    try:
        logger.info(f"Starting newsletter generation task {task_id}")
        
        # Build command
        cmd = [sys.executable, "-m", "src.newsletter_bot", "generate"]
        if dry_run:
            cmd.append("--dry-run")
        
        # Run in subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=1800)
        
        # Update task status
        if process.returncode == 0:
            running_tasks[task_id].update({
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "output": stdout.decode(),
                "success": True
            })
            logger.info(f"Task {task_id} completed successfully")
        else:
            running_tasks[task_id].update({
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat(),
                "output": stdout.decode(),
                "error": stderr.decode(),
                "success": False
            })
            logger.error(f"Task {task_id} failed: {stderr.decode()}")
            
    except asyncio.TimeoutError:
        running_tasks[task_id].update({
            "status": "timeout",
            "completed_at": datetime.utcnow().isoformat(),
            "error": "Task timed out after 30 minutes",
            "success": False
        })
        logger.error(f"Task {task_id} timed out")
        
    except Exception as e:
        running_tasks[task_id].update({
            "status": "error", 
            "completed_at": datetime.utcnow().isoformat(),
            "error": str(e),
            "success": False
        })
        logger.error(f"Task {task_id} error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)