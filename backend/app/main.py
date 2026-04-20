from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
import uuid
import asyncio
import io
import csv
from pydantic import BaseModel

from . import models, database, scraper, validator, auth, worker
from .database import engine, get_db

# Create tables
database.ensure_legacy_schema_compatibility()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="LeadGen SaaS Pro API")

CORS_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import logging
    logging.error(f"Global exception caught: {exc}", exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin") or CORS_ORIGINS[0],
            "Access-Control-Allow-Credentials": "true"
        }
    )

@app.get("/")
async def root():
    return {"message": "LeadGen Pro API is running", "version": "2.0.0"}

# --- SCHEMAS ---

class PaymentCreate(BaseModel):
    plan_name: str
    amount: float
    account_name: str
    upi_id: str

# --- AUTH ENDPOINTS ---

@app.post("/signup")
def signup(user_data: dict, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == user_data["username"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = models.User(
        username=user_data["username"],
        email=user_data.get("email"),
        hashed_password=auth.get_password_hash(user_data["password"]),
        credits=100, # Initial trial credits
        role=models.UserRole.USER.value,
        plan="free",
        is_approved=0 # Default to 0 (False/Pending)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created. Awaiting admin approval.", "username": new_user.username}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Your account is pending admin approval"
        )
    
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
async def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "credits": current_user.credits,
        "role": current_user.role,
        "plan": current_user.plan,
        "is_approved": bool(current_user.is_approved),
        "is_admin": auth.is_admin(current_user),
    }

# --- MONETIZATION ENDPOINTS ---

@app.post("/credits/purchase")
async def purchase_credits(data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Simulation of payment success
    amount = data.get("amount", 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    current_user.credits += amount
    db.commit()
    return {"message": "Purchase successful", "new_balance": current_user.credits}


@app.post("/admin/promote")
async def promote_user(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    """Make any user an admin. Only callable by existing admins."""
    target_username = data.get("username")
    if not target_username:
        raise HTTPException(status_code=422, detail="'username' field is required")

    target = db.query(models.User).filter(models.User.username == target_username).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User '{target_username}' not found")

    target.role = models.UserRole.ADMIN.value
    db.commit()
    return {"message": f"User '{target_username}' promoted to admin"}

# --- PAYMENT ENDPOINTS ---

@app.post("/payments")
async def create_payment_request(
    payment: PaymentCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    new_payment = models.Payment(
        user_id=current_user.id,
        plan_name=payment.plan_name,
        amount=payment.amount,
        account_name=payment.account_name,
        upi_id=payment.upi_id,
        status=models.PaymentStatus.PENDING
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return {"message": "Payment request submitted. Waiting for admin confirmation.", "id": new_payment.id}

@app.get("/admin/payments")
async def get_all_payments(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    query = db.query(models.Payment)
    if status:
        query = query.filter(models.Payment.status == models.PaymentStatus(status))
    
    payments = query.order_by(desc(models.Payment.created_at)).all()
    
    # Include user info in response
    result = []
    for p in payments:
        user = db.query(models.User).filter(models.User.id == p.user_id).first()
        result.append({
            "id": p.id,
            "plan_name": p.plan_name,
            "amount": p.amount,
            "account_name": p.account_name,
            "upi_id": p.upi_id,
            "status": p.status.value,
            "created_at": p.created_at,
            "username": user.username if user else "Unknown"
        })
    return result

@app.post("/admin/payments/{payment_id}/approve")
async def approve_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status != models.PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="Payment is not pending")
    
    # Calculate credits based on plan
    plan_credits = {
        "starter": 100,
        "pro": 500,
        "enterprise": 2500
    }
    credits_to_add = plan_credits.get(payment.plan_name.lower(), 0)
    
    user = db.query(models.User).filter(models.User.id == payment.user_id).first()
    if user:
        user.credits += credits_to_add
        user.plan = payment.plan_name.lower()
        payment.status = models.PaymentStatus.APPROVED
        db.commit()
        return {"message": f"Payment approved. {credits_to_add} credits added to User {user.username}."}
    
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/admin/payments/{payment_id}/reject")
async def reject_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment.status = models.PaymentStatus.REJECTED
    db.commit()
    return {"message": "Payment request rejected"}

# --- ADMIN USER MANAGEMENT ---

@app.get("/admin/users")
async def get_all_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    users = db.query(models.User).order_by(desc(models.User.created_at)).all()
    return [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "plan": u.plan,
        "credits": u.credits,
        "is_approved": bool(u.is_approved),
        "created_at": u.created_at
    } for u in users]

@app.post("/admin/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_approved = 1
    db.commit()
    return {"message": f"User {user.username} approved successfully."}

@app.post("/admin/users/{user_id}/reject")
async def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # We could delete or just keep as unapproved. For rejection, let's just keep as unapproved 0.
    # Or set to -1 for "Totally Rejected/Banned".
    user.is_approved = 0 
    db.commit()
    return {"message": f"User {user.username} rejected (remains unapproved)."}

# --- SCRAPER ENDPOINTS ---

@app.post("/jobs")
async def create_job(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    input_data = data.get("input")
    job_type = data.get("type", "maps")
    location = data.get("location", "")

    if not input_data:
        raise HTTPException(status_code=422, detail="'input' field is required")

    # Pricing logic
    pricing = {
        "maps": 10,
        "url": 5
    }
    cost = pricing.get(job_type, 1)

    # ── Credit check: skip entirely for admin users ──────────────────────────
    is_admin = auth.is_admin(current_user)
    if not is_admin:
        if current_user.credits < cost:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient credits. You need {cost} credits but have {current_user.credits}. Please upgrade.",
            )
        # Atomic deduction for regular users only
        current_user.credits -= cost
        db.commit()
        db.refresh(current_user)

    new_job = models.Job(
        user_id=current_user.id,
        input_data=input_data,
        location=location,
        type=models.JobType(job_type),
        status=models.JobStatus.PENDING,
        credit_cost=cost
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # Try Celery first (requires Redis running). Fall back to FastAPI BackgroundTasks.
    dispatched_via = "celery"
    try:
        worker.process_leadgen_job.delay(new_job.id)
    except Exception:
        # Redis / Celery not available — run in-process as a background task
        dispatched_via = "background_task"
        background_tasks.add_task(worker.run_job_sync, new_job.id)

    return {
        "job_id": new_job.id,
        "status": "queued",
        "remaining_credits": current_user.credits,
        "dispatched_via": dispatched_via,
        "note": "Job is being processed in the background"
    }

@app.get("/jobs/{job_id}")
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

@app.get("/results")
async def get_results(
    status: Optional[str] = None, 
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # PAGINATION UPGRADE
    user_job_ids = db.query(models.Job.id).filter(models.Job.user_id == current_user.id).subquery()
    query = db.query(models.Company).filter(models.Company.job_id.in_(user_job_ids))
    
    if status:
        query = query.filter(models.Company.validation_status == status)
    
    total = query.count()
    results = query.order_by(desc(models.Company.created_at)).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": results
    }

@app.get("/stats")
async def get_stats(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    user_job_ids = db.query(models.Job.id).filter(models.Job.user_id == current_user.id).subquery()
    total = db.query(models.Company).filter(models.Company.job_id.in_(user_job_ids)).count()
    valid = db.query(models.Company).filter(models.Company.job_id.in_(user_job_ids), models.Company.validation_status == "valid").count()

    return {
        "total_leads": total,
        "valid_leads": valid,
        "credits": current_user.credits,
        "jobs_count": db.query(models.Job).filter(models.Job.user_id == current_user.id).count()
    }



@app.delete("/results/clear")
async def clear_results(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Delete ALL scraped leads (Company rows) belonging to the current user.
    Also removes the associated Job records so job count resets cleanly.
    Returns updated stats after deletion.
    """
    # Get all job IDs owned by this user
    user_job_ids = (
        db.query(models.Job.id)
        .filter(models.Job.user_id == current_user.id)
        .subquery()
    )

    # Delete all Company rows linked to those jobs
    deleted_leads = (
        db.query(models.Company)
        .filter(models.Company.job_id.in_(user_job_ids))
        .delete(synchronize_session="fetch")
    )

    # Delete all Job rows
    deleted_jobs = (
        db.query(models.Job)
        .filter(models.Job.user_id == current_user.id)
        .delete(synchronize_session="fetch")
    )

    db.commit()

    return {
        "message": f"Cleared {deleted_leads} leads and {deleted_jobs} jobs.",
        "deleted_leads": deleted_leads,
        "deleted_jobs": deleted_jobs,
    }


@app.get("/results/export")
async def export_results_csv(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Export all leads as a properly structured CSV.
    - Uses utf-8-sig (BOM) so Excel opens it without encoding issues.
    - Each field is cleanly sanitised (no garbled characters).
    """
    user_job_ids = (
        db.query(models.Job.id)
        .filter(models.Job.user_id == current_user.id)
        .subquery()
    )
    query = db.query(models.Company).filter(models.Company.job_id.in_(user_job_ids))
    if status_filter:
        query = query.filter(models.Company.validation_status == status_filter)

    rows = query.order_by(desc(models.Company.created_at)).all()

    def _clean(value) -> str:
        """Strip None and fix mojibake by re-encoding via latin-1 if needed."""
        if value is None:
            return ""
        text = str(value).strip()
        # Fix common encoding artifact: attempt latin-1 -> utf-8 round-trip
        try:
            text = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return text

    def generate():
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Header row
        writer.writerow([
            "CompanyName", "Email", "Phone", "Website",
            "Address", "Rating", "Reviews", "Category", "Status",
        ])
        yield "\ufeff"  # UTF-8 BOM — makes Excel auto-detect encoding
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        for row in rows:
            writer.writerow([
                _clean(row.company_name),
                _clean(row.email),
                _clean(row.phone),
                _clean(row.website),
                _clean(row.address),
                _clean(row.rating),
                _clean(row.reviews_count),
                _clean(row.category),
                _clean(row.validation_status),
            ])
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    filename = f"leads_export_{current_user.username}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
