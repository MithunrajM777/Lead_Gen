from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from .. import models
from ..services import auth
from ..database import get_db

router = APIRouter()

@router.get("/users")
async def get_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_admin)):
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

@router.post("/users/{user_id}/approve")
async def approve_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = 1
    db.commit()
    return {"message": f"User {user.username} approved successfully."}

@router.post("/users/{user_id}/reject")
async def reject_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = 0 
    db.commit()
    return {"message": f"User {user.username} rejected (remains unapproved)."}

@router.get("/payments")
async def get_all_payments(status: Optional[str] = None, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_admin)):
    query = db.query(models.Payment)
    if status:
        query = query.filter(models.Payment.status == models.PaymentStatus(status))
    payments = query.order_by(desc(models.Payment.created_at)).all()
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

@router.post("/payments/{payment_id}/approve")
async def approve_payment(payment_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_admin)):
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment: raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status != models.PaymentStatus.PENDING: raise HTTPException(status_code=400, detail="Payment is not pending")
    
    plan_credits = {"starter": 100, "pro": 500, "enterprise": 2500}
    credits_to_add = plan_credits.get(payment.plan_name.lower(), 0)
    user = db.query(models.User).filter(models.User.id == payment.user_id).first()
    if user:
        user.credits += credits_to_add
        user.plan = payment.plan_name.lower()
        payment.status = models.PaymentStatus.APPROVED
        db.commit()
        return {"message": f"Payment approved. {credits_to_add} credits added."}
    raise HTTPException(status_code=404, detail="User not found")
