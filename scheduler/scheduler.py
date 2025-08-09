"""Newsletter generation scheduling system."""

import logging
from datetime import datetime
from typing import Optional

from celery import Celery
from celery.schedules import crontab

from src.models.settings import Settings

logger = logging.getLogger(__name__)

# Initialize Celery app
app = Celery('newsletter-scheduler')

# Configure Celery
app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        'generate-weekly-newsletter': {
            'task': 'scheduler.scheduler.generate_newsletter_task',
            'schedule': crontab(hour=9, minute=0, day_of_week=6),  # Saturday 9AM UTC
        },
    },
)


@app.task
def generate_newsletter_task(dry_run: bool = False) -> dict:
    """Celery task to generate newsletter."""
    import subprocess
    import sys
    
    try:
        logger.info(f"Starting scheduled newsletter generation (dry_run={dry_run})")
        
        # Build command
        cmd = [sys.executable, "-m", "src.newsletter_bot", "generate"]
        if dry_run:
            cmd.append("--dry-run")
        
        # Run newsletter generation
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Newsletter generation completed successfully")
            return {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "output": result.stdout,
                "dry_run": dry_run
            }
        else:
            logger.error(f"Newsletter generation failed: {result.stderr}")
            return {
                "status": "error", 
                "timestamp": datetime.utcnow().isoformat(),
                "error": result.stderr,
                "output": result.stdout,
                "dry_run": dry_run
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Newsletter generation timed out")
        return {
            "status": "timeout",
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Task timed out after 30 minutes",
            "dry_run": dry_run
        }
    except Exception as e:
        logger.error(f"Unexpected error in newsletter task: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(), 
            "error": str(e),
            "dry_run": dry_run
        }


@app.task
def health_check_task() -> dict:
    """Celery task for system health checks."""
    import subprocess
    import sys
    
    try:
        logger.info("Running scheduled health check")
        
        result = subprocess.run(
            [sys.executable, "-m", "src.newsletter_bot", "health"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return {
            "status": "success" if result.returncode == 0 else "warning",
            "timestamp": datetime.utcnow().isoformat(),
            "output": result.stdout,
            "return_code": result.returncode
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


if __name__ == '__main__':
    app.start()