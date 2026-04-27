from .. import models, database
from . import scraper, validator
from ..database import SessionLocal
import logging
import json
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkerTask:
    """Helper to simulate the Celery task context (db session)"""
    def __init__(self):
        self.db = SessionLocal()
    
    def close(self):
        self.db.close()

async def run_job(job_id: int):
    task = WorkerTask()
    try:
        await async_process_job(task, job_id)
    finally:
        task.close()

async def run_bulk_job(job_id: int):
    task = WorkerTask()
    try:
        await async_process_bulk_job(task, job_id)
    finally:
        task.close()

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
        is_admin = user and user.role == "admin"

        results = []
        credits_deducted = False  # deduct only after first successful lead

        try:
            if job.type == models.JobType.MAPS:
                # ── Query Building ──────────────────────────────────────────
                keyword = job.input_data
                location = job.location
                pincodes = []

                # Check if input_data is JSON (complex input)
                try:
                    data = json.loads(job.input_data)
                    if isinstance(data, dict):
                        keyword = data.get("keyword", keyword)
                        pincodes = data.get("pincodes", [])
                        location = data.get("location", location)
                except:
                    pass

                queries = []
                if pincodes and len(pincodes) > 0:
                    queries = [f"{keyword} in {pc}" for pc in pincodes]
                elif location:
                    if "district" in location.lower():
                        queries = [f"{keyword} in {location}"]
                    else:
                        queries = [f"{keyword} in {location} district"]
                else:
                    queries = [keyword]

                seen_company_names = set()
                seen_ratings = set()

                for query in queries:
                    # Check for cancellation before starting a new query
                    db.refresh(job)
                    if job.status == models.JobStatus.STOPPED or not scraper.active_jobs.get(job_id, True):
                        break

                    # keyword and location for scraper function
                    # Since we built the full query, we pass it as keyword and empty location
                    async for item in scraper.scrape_google_maps(query, "", max_results=50, job_id=job_id):
                        # Check for cancellation signal (DB and memory)
                        db.refresh(job)
                        if job.status == models.JobStatus.STOPPED or not scraper.active_jobs.get(job_id, True):
                            logger.info(f"Worker: Job {job_id} stopped by user.")
                            job.status = models.JobStatus.STOPPED
                            db.commit()
                            break

                        # NEW: Validation layer
                        if not validator.is_valid_business_lead(item, keyword=keyword, location=location, seen_ratings=seen_ratings):
                            continue

                        # Deduplicate across multiple queries
                        c_name = item.get("company_name", "").strip().lower()
                        if not c_name or c_name in seen_company_names:
                            continue
                        seen_company_names.add(c_name)

                        results.append(item)
                        # Inline processing for worker (saving as we go)
                        try:
                            validated = validator.clean_and_validate(item)
                            
                            # Duplicate check: domain OR email
                            email = validated.get("email")
                            website = validated.get("website")
                            domain = ""
                            if website:
                                domain = urlparse(website).netloc.replace("www.", "")
                            
                            existing = None
                            if email:
                                existing = db.query(models.Company).filter(models.Company.email == email).first()
                            if not existing and domain:
                                existing = db.query(models.Company).filter(models.Company.website.contains(domain)).first()
                                
                            if existing:
                                logger.info(f"Skipping duplicate: {validated.get('company_name')}")
                                continue

                            company = models.Company(job_id=job_id, **validated)
                            db.add(company)
                            db.commit()  # Save each one

                            # Deduct credits on first successful lead
                            if not is_admin and not credits_deducted and user:
                                db.refresh(user)
                                user.credits -= job.credit_cost
                                db.commit()
                                credits_deducted = True
                                logger.info(f"Worker: Deducted {job.credit_cost} credits from user {user.id} for job {job_id}")
                        except Exception as e:
                            logger.error(f"Worker failed to save item: {e}")
            elif job.type == models.JobType.URL:
                raw_data = await scraper.scrape_site(job.input_data)
                results = [raw_data]
                validated = validator.clean_and_validate(raw_data)
                company = models.Company(job_id=job_id, **validated)
                db.add(company)
                db.commit()
                # Deduct credits for URL scraping on success
                if not is_admin and not credits_deducted and user:
                    db.refresh(user)
                    user.credits -= job.credit_cost
                    db.commit()
                    credits_deducted = True
        except Exception as e:
            logger.error(f"Scraping failed for job {job_id}: {e}")
            job.status = models.JobStatus.FAILED
            db.commit()
            # No refund needed — credits were not deducted upfront
            return

        # 0 results found — no charge
        if not results:
            logger.info(f"0 leads found for job {job_id}. No credits deducted.")
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
        # Clean up active jobs
        if job_id in scraper.active_jobs:
            del scraper.active_jobs[job_id]
        db.close()


async def async_process_bulk_job(task, job_id: int):
    db = task.db
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job: return
        
        job.status = models.JobStatus.PROCESSING
        db.commit()

        data = json.loads(job.input_data)
        urls = data.get("urls", [])
        
        user = db.query(models.User).filter(models.User.id == job.user_id).first()
        is_admin = user and user.role == "admin"
        
        semaphore = asyncio.Semaphore(5) # Concurrency limit: 5

        async def scrape_and_save(url):
            async with semaphore:
                # Check for stop signal
                db.refresh(job)
                if job.status == models.JobStatus.STOPPED or not scraper.active_jobs.get(job_id, True):
                    return
                
                try:
                    raw_data = await scraper.scrape_site(url)
                    validated = validator.clean_and_validate(raw_data)
                    
                    # Duplicate check
                    email = validated.get("email")
                    domain = urlparse(url).netloc.replace("www.", "")
                    
                    existing = None
                    if email:
                        existing = db.query(models.Company).filter(models.Company.email == email).first()
                    if not existing and domain:
                        existing = db.query(models.Company).filter(models.Company.website.contains(domain)).first()
                        
                    if existing:
                        logger.info(f"Skipping duplicate bulk: {url}")
                        return False

                    company = models.Company(job_id=job_id, **validated)
                    db.add(company)
                    db.commit()
                    return True
                except Exception as e:
                    logger.error(f"Bulk worker failed for {url}: {e}")
                    return False

        tasks = [scrape_and_save(url) for url in urls]
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r)

        # Deduct credits if at least one success
        if success_count > 0 and not is_admin and user:
            db.refresh(user)
            user.credits -= job.credit_cost
            db.commit()

        job.status = models.JobStatus.COMPLETED
        db.commit()
        logger.info(f"Bulk job {job_id} completed with {success_count} leads.")
    except Exception as e:
        logger.error(f"Error in bulk worker {job_id}: {e}")
        if job:
            job.status = models.JobStatus.FAILED
            db.commit()
    finally:
        if job_id in scraper.active_jobs:
            del scraper.active_jobs[job_id]


def run_job_sync(job_id: int):
    """
    Synchronous wrapper for use with FastAPI BackgroundTasks
    when Celery / Redis is not available.
    """
    asyncio.run(async_process_job_standalone(job_id))

def run_bulk_job_sync(job_id: int):
    asyncio.run(async_process_bulk_job_standalone(job_id))


async def async_process_bulk_job_standalone(job_id: int):
    db = SessionLocal()
    job = None
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job: return
        
        job.status = models.JobStatus.PROCESSING
        db.commit()

        data = json.loads(job.input_data)
        urls = data.get("urls", [])
        
        user = db.query(models.User).filter(models.User.id == job.user_id).first()
        is_admin = user and user.role == "admin"
        
        semaphore = asyncio.Semaphore(5)

        async def scrape_and_save(url):
            async with semaphore:
                db.refresh(job)
                if job.status == models.JobStatus.STOPPED or not scraper.active_jobs.get(job_id, True):
                    return
                try:
                    raw_data = await scraper.scrape_site(url)
                    validated = validator.clean_and_validate(raw_data)
                    
                    # Duplicate check
                    email = validated.get("email")
                    domain = urlparse(url).netloc.replace("www.", "")
                    
                    existing = None
                    if email:
                        existing = db.query(models.Company).filter(models.Company.email == email).first()
                    if not existing and domain:
                        existing = db.query(models.Company).filter(models.Company.website.contains(domain)).first()
                        
                    if existing:
                        return False

                    company = models.Company(job_id=job_id, **validated)
                    db.add(company)
                    db.commit()
                    return True
                except Exception as e:
                    logger.error(f"[Fallback] Bulk worker failed for {url}: {e}")
                    return False

        tasks = [scrape_and_save(url) for url in urls]
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r)

        if success_count > 0 and not is_admin and user:
            db.refresh(user)
            user.credits -= job.credit_cost
            db.commit()

        job.status = models.JobStatus.COMPLETED
        db.commit()
        logger.info(f"[Fallback] Bulk job {job_id} completed.")
    except Exception as e:
        logger.error(f"[Fallback] Error in bulk worker {job_id}: {e}")
        if job:
            job.status = models.JobStatus.FAILED
            db.commit()
    finally:
        if job_id in scraper.active_jobs:
            del scraper.active_jobs[job_id]
        db.close()
