from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, select
from typing import List, Optional
import io
import csv
import json
import pandas as pd
import traceback

from .. import models, database
from ..services import scraper, validator, worker, auth
from ..database import get_db

router = APIRouter()

class ScraperRequest(json.BaseModel if hasattr(json, 'BaseModel') else object): 
    # Wait, I should import BaseModel from pydantic
    pass

from pydantic import BaseModel

class ScraperRequest(BaseModel):
    input: str
    location: Optional[str] = ""
    pincodes: Optional[List[str]] = []
    type: str = "maps"

@router.post("/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    filename = file.filename.lower()
    
    # File size limit: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max size is 10MB.")
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"User {current_user.username} uploading file: {filename} ({len(content)} bytes)")
    
    df = None
    
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Invalid file format. Please upload CSV or XLSX.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")

    if "website_url" not in df.columns:
        raise HTTPException(status_code=422, detail="Excel must contain a 'website_url' column.")

    urls = df["website_url"].dropna().tolist()
    if not urls:
        raise HTTPException(status_code=400, detail="No URLs found in the file.")

    urls = [u.strip() for u in urls if u and isinstance(u, str)]
    
    cost_per_url = 5
    total_cost = len(urls) * cost_per_url
    if not auth.is_admin(current_user) and current_user.credits < total_cost:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient credits. You need {total_cost} credits for {len(urls)} URLs.",
        )

    new_job = models.Job(
        user_id=current_user.id,
        input_data=json.dumps({"urls": urls}),
        type=models.JobType.URL,
        status=models.JobStatus.PENDING,
        credit_cost=total_cost
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    try:
        background_tasks.add_task(worker.run_bulk_job, new_job.id)
    except Exception as e:
        logger.error(f"Failed to start background task: {e}")

    scraper.active_jobs[new_job.id] = True

    return {
        "job_id": new_job.id,
        "status": "queued",
        "url_count": len(urls),
        "total_cost": total_cost
    }

@router.post("/jobs")
async def create_job(
    request: ScraperRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    input_data = request.input
    job_type = request.type
    location = request.location
    pincodes = request.pincodes

    if not input_data:
        raise HTTPException(status_code=422, detail="'input' (keyword) field is required")

    pricing = {"maps": 10, "url": 5}
    cost = pricing.get(job_type, 1)

    is_admin = auth.is_admin(current_user)
    if not is_admin:
        if current_user.credits < cost:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient credits. You need {cost} credits.",
            )

    stored_input = input_data
    if pincodes and len(pincodes) > 0:
        stored_input = json.dumps({
            "keyword": input_data,
            "pincodes": pincodes,
            "location": location
        })

    new_job = models.Job(
        user_id=current_user.id,
        input_data=stored_input,
        location=location,
        type=models.JobType(job_type),
        status=models.JobStatus.PENDING,
        credit_cost=cost
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    try:
        background_tasks.add_task(worker.run_job, new_job.id)
    except Exception as e:
        logger.error(f"Failed to start background task: {e}")

    scraper.active_jobs[new_job.id] = True

    return {
        "job_id": new_job.id,
        "status": "queued",
        "remaining_credits": current_user.credits,
    }

@router.post("/jobs/stream")
async def create_streaming_job(
    request: ScraperRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    input_data = request.input
    job_type = request.type
    location = request.location
    pincodes = request.pincodes

    if not input_data:
        raise HTTPException(status_code=422, detail="'input' (keyword) field is required")

    pricing = {"maps": 10, "url": 5}
    cost = pricing.get(job_type, 1)

    is_admin = auth.is_admin(current_user)
    if not is_admin:
        if current_user.credits < cost:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient credits.",
            )

    stored_input = input_data
    if pincodes and len(pincodes) > 0:
        stored_input = json.dumps({
            "keyword": input_data,
            "pincodes": pincodes,
            "location": location
        })

    new_job = models.Job(
        user_id=current_user.id,
        input_data=stored_input,
        location=location,
        type=models.JobType(job_type),
        status=models.JobStatus.PROCESSING,
        credit_cost=cost
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    async def event_generator():
        yield f"data: {json.dumps({'job_id': new_job.id})}\n\n"
        leads_saved = 0
        credits_deducted = False

        try:
            if job_type == "maps":
                queries = []
                if pincodes and len(pincodes) > 0:
                    queries = [f"{input_data} in {pc}" for pc in pincodes]
                elif location:
                    if "district" in location.lower():
                        queries = [f"{input_data} in {location}"]
                    else:
                        queries = [f"{input_data} in {location} district"]
                else:
                    queries = [input_data]

                seen_company_names = set()

                for query in queries:
                    if not scraper.active_jobs.get(new_job.id, True):
                        break

                    async for item in scraper.scrape_google_maps(query, "", max_results=50, job_id=new_job.id):
                        if not scraper.active_jobs.get(new_job.id, True):
                            break

                        c_name = item.get("company_name", "").strip().lower()
                        if not c_name or c_name in seen_company_names:
                            continue
                        seen_company_names.add(c_name)

                        try:
                            validated = validator.clean_and_validate(item)
                            company = models.Company(job_id=new_job.id, **validated)
                            db.add(company)
                            db.commit()
                            leads_saved += 1

                            if not is_admin and not credits_deducted:
                                db.refresh(current_user)
                                current_user.credits -= cost
                                db.commit()
                                credits_deducted = True

                            yield f"data: {json.dumps(validated)}\n\n"
                        except Exception as e:
                            print(f"Error saving streamed item: {e}")

            elif job_type == "url":
                raw_data = await scraper.scrape_site(input_data)
                validated = validator.clean_and_validate(raw_data)
                
                company = models.Company(job_id=new_job.id, **validated)
                db.add(company)
                db.commit()
                leads_saved += 1
                
                if not is_admin and not credits_deducted:
                    db.refresh(current_user)
                    current_user.credits -= cost
                    db.commit()
                    credits_deducted = True
                    
                yield f"data: {json.dumps(validated)}\n\n"

            db.refresh(new_job)
            if new_job.status == models.JobStatus.STOPPED or not scraper.active_jobs.get(new_job.id, True):
                new_job.status = models.JobStatus.STOPPED
                yield f"data: {json.dumps({'stopped': True})}\n\n"
            else:
                new_job.status = models.JobStatus.COMPLETED
                yield "data: {\"done\": true}\n\n"

            db.commit()
        except Exception as e:
            traceback.print_exc()
            try:
                db.refresh(new_job)
                if new_job.status != models.JobStatus.STOPPED:
                    new_job.status = models.JobStatus.FAILED
                    db.commit()
            except Exception: pass
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if new_job.id in scraper.active_jobs:
                del scraper.active_jobs[new_job.id]

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/jobs/{job_id}/stop")
async def stop_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    job = db.query(models.Job).filter(models.Job.id == job_id, models.Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = models.JobStatus.STOPPED
    db.commit()
    scraper.active_jobs[job_id] = False
    return {"message": "Job stopped"}

@router.get("/jobs/{job_id}")
async def get_job(job_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    job = db.query(models.Job).filter(models.Job.id == job_id, models.Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    results_count = db.query(models.Company).filter(models.Company.job_id == job.id).count()
    return {
        "id": job.id,
        "status": job.status.value,
        "type": job.type.value,
        "input": job.input_data,
        "results_count": results_count
    }

@router.get("/results")
async def get_results(
    status: Optional[str] = None, 
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    user_job_ids = select(models.Job.id).filter(models.Job.user_id == current_user.id)
    query = db.query(models.Company).filter(models.Company.job_id.in_(user_job_ids))
    
    if status:
        query = query.filter(models.Company.validation_status == status)
    
    total = query.count()
    results = query.order_by(desc(models.Company.created_at)).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": results
    }

@router.delete("/results/clear")
async def clear_results(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user_job_ids = select(models.Job.id).filter(models.Job.user_id == current_user.id)
    deleted_leads = db.query(models.Company).filter(models.Company.job_id.in_(user_job_ids)).delete(synchronize_session="fetch")
    deleted_jobs = db.query(models.Job).filter(models.Job.user_id == current_user.id).delete(synchronize_session="fetch")
    db.commit()
    return {"message": f"Cleared {deleted_leads} leads and {deleted_jobs} jobs."}

@router.get("/results/export")
async def export_results_csv(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user_job_ids = select(models.Job.id).filter(models.Job.user_id == current_user.id)
    query = db.query(models.Company).filter(models.Company.job_id.in_(user_job_ids))
    if status_filter:
        query = query.filter(models.Company.validation_status == status_filter)

    rows = query.order_by(desc(models.Company.created_at)).all()

    def generate():
        import io
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        writer.writerow(["CompanyName", "Email", "Phone", "Website", "Address", "Rating", "Reviews", "Category", "Status"])
        yield "\ufeff"
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
        for row in rows:
            writer.writerow([row.company_name, row.email, row.phone, row.website, row.address, row.rating, row.reviews_count, row.category, row.validation_status])
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    return StreamingResponse(generate(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=leads.csv"})
