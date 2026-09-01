from sqlalchemy import Column, Integer, String, DateTime, Boolean
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    title = Column(String)
    description = Column(String, nullable=True)
    category = Column(String)  # Work, Personal, Urgent
    priority = Column(String)  # High, Medium, Low
    deadline = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)  # NEW: soft delete
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # NEW: when deleted