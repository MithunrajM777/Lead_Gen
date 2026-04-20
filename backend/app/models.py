from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base


class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobType(enum.Enum):
    URL = "url"
    KEYWORD = "keyword"
    MAPS = "maps"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    credits = Column(Integer, default=100)
    plan = Column(String, default="free") # "free", "starter", "pro", "enterprise"
    is_active = Column(Integer, default=1)
    role = Column(String, default=UserRole.USER.value)  # "admin" or "user"
    is_approved = Column(Integer, default=0) # 0 = Pending, 1 = Approved
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="user")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(JobType))
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    input_data = Column(Text)  # URL, Keyword, or Search Term
    location = Column(String, nullable=True) # For Maps/Search
    credit_cost = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="jobs")
    results = relationship("Company", back_populates="job")

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    company_name = Column(String, index=True)
    phone = Column(String)
    email = Column(String)
    address = Column(Text)
    website = Column(String)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, default=0)
    category = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    validation_status = Column(String)  # "valid", "invalid", "unverified"
    validation_details = Column(JSON, nullable=True)
    source = Column(String) # e.g., "google_maps", "direct_scrape"
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="results")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plan_name = Column(String)
    amount = Column(Float)
    account_name = Column(String)
    upi_id = Column(String)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
