import asyncio
from celery import Task
from .celery_app import celery_app
from . import models, scraper, validator, database
from .database import SessionLocal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseTask(Task):
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None

@celery_app.task(bind=True, base=DatabaseTask)
def process_leadgen_job(self, job_id: int):
    # This needs to run in an event loop because scrapers are async
    return asyncio.run(async_process_job(self, job_id))

async def async_process_job(task, job_id: int):
    db = task.db
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = models.JobStatus.PROCESSING
        db.commit()

        user = db.query(models.User).filter(models.User.id == job.user_id).first()
        
        results = []
        try:
            if job.type == models.JobType.MAPS:
                results = await scraper.scrape_google_maps(job.input_data, job.location, max_results=20)
            elif job.type == models.JobType.URL:
                raw_data = await scraper.scrape_site(job.input_data)
                results = [raw_data]
        except Exception as e:
            logger.error(f"Scraping failed for job {job_id}: {e}")
            job.status = models.JobStatus.FAILED
            db.commit()
            # Refund logic if nothing happened
            user.credits += job.credit_cost
            db.commit()
            return

        # If 0 results found, refund credits (Senior Architect refinement)
        if not results:
            logger.info(f"0 leads found for job {job_id}. Refunding {job.credit_cost} credits.")
            user.credits += job.credit_cost
            job.status = models.JobStatus.COMPLETED
            db.commit()
            return

        processed_count = 0
        for item in results:
            try:
                # Lightweight email/phone enrichment via httpx — no extra browser needed
                if job.type == models.JobType.MAPS and item.get("website"):
                    try:
                        enriched = await scraper.enrich_from_website(item["website"])
                        item["email"] = item.get("email") or enriched.get("email", "")
                        item["phone"] = item.get("phone") or enriched.get("phone", "")
                    except Exception as enr_err:
                        logger.warning(f"Enrichment failed for {item.get('website')}: {enr_err}")

                validated = validator.clean_and_validate(item)
                company = models.Company(
                    job_id=job_id,
                    **validated
                )
                db.add(company)
                processed_count += 1
                
                # Commit every 5 results for large jobs to show progress
                if processed_count % 5 == 0:
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to process result in job {job_id}: {e}")

        job.status = models.JobStatus.COMPLETED
        db.commit()
        logger.info(f"Job {job_id} completed successfully with {processed_count} leads.")

    except Exception as e:
        logger.error(f"Unexpected error in worker for job {job_id}: {e}")
        if job:
            job.status = models.JobStatus.FAILED
            db.commit()
    finally:
        db.close()


def run_job_sync(job_id: int):
    """
    Synchronous wrapper for use with FastAPI BackgroundTasks
    when Celery / Redis is not available.
    """
    asyncio.run(async_process_job_standalone(job_id))


async def async_process_job_standalone(job_id: int):
    """Standalone version of async_process_job that creates its own DB session."""
    db = SessionLocal()
    job = None
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job:
            logger.error(f"[Fallback] Job {job_id} not found")
            return

        job.status = models.JobStatus.PROCESSING
        db.commit()

        user = db.query(models.User).filter(models.User.id == job.user_id).first()

        results = []
        try:
            if job.type == models.JobType.MAPS:
                results = await scraper.scrape_google_maps(job.input_data, job.location, max_results=20)
            elif job.type == models.JobType.URL:
                raw_data = await scraper.scrape_site(job.input_data)
                results = [raw_data]
        except Exception as e:
            logger.error(f"[Fallback] Scraping failed for job {job_id}: {e}")
            job.status = models.JobStatus.FAILED
            if user:
                user.credits += job.credit_cost
            db.commit()
            return

        if not results:
            if user:
                user.credits += job.credit_cost
            job.status = models.JobStatus.COMPLETED
            db.commit()
            return

        processed_count = 0
        for item in results:
            try:
                # Lightweight email/phone enrichment via httpx — no extra browser needed
                if job.type == models.JobType.MAPS and item.get("website"):
                    try:
                        enriched = await scraper.enrich_from_website(item["website"])
                        item["email"] = item.get("email") or enriched.get("email", "")
                        item["phone"] = item.get("phone") or enriched.get("phone", "")
                    except Exception as enr_err:
                        logger.warning(f"[Fallback] Enrichment failed for {item.get('website')}: {enr_err}")

                validated = validator.clean_and_validate(item)
                company = models.Company(job_id=job_id, **validated)
                db.add(company)
                processed_count += 1

                if processed_count % 5 == 0:
                    db.commit()
            except Exception as e:
                logger.error(f"[Fallback] Failed to process result in job {job_id}: {e}")

        job.status = models.JobStatus.COMPLETED
        db.commit()
        logger.info(f"[Fallback] Job {job_id} completed with {processed_count} leads.")

    except Exception as e:
        logger.error(f"[Fallback] Unexpected error for job {job_id}: {e}")
        if job:
            job.status = models.JobStatus.FAILED
            db.commit()
    finally:
        db.close()
