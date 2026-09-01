from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import User, Task
from pydantic import BaseModel
import hashlib
from datetime import datetime, timedelta
from jose import jwt
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = "your-super-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# ---------- Request Models ----------
class SignupRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TaskCreate(BaseModel):
    title: str
    description: str = None
    category: str
    priority: str
    deadline: str = None

class TaskUpdate(BaseModel):
    title: str = None
    description: str = None
    category: str = None
    priority: str = None
    deadline: str = None
    is_completed: bool = None

# ---------- Helper Functions ----------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ---------- Auth Endpoints ----------
@app.post("/signup")
def signup(user_data: SignupRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = hash_password(user_data.password)
    new_user = User(email=user_data.email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully", "id": new_user.id}

@app.post("/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    hashed_input = hash_password(login_data.password)
    if user.password != hashed_input:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id}

# ---------- Task Endpoints ----------
@app.get("/tasks")
def get_tasks(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Only return tasks that are NOT deleted
    tasks = db.query(Task).filter(Task.user_id == user_id, Task.is_deleted == False).order_by(Task.deadline.asc()).all()
    return tasks

@app.get("/tasks/history")
def get_history(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Return ONLY deleted tasks
    tasks = db.query(Task).filter(Task.user_id == user_id, Task.is_deleted == True).order_by(Task.deleted_at.desc()).all()
    return tasks

@app.get("/tasks/upcoming")
def get_upcoming_tasks(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get tasks due in the next 3 days
    now = datetime.utcnow()
    three_days_later = now + timedelta(days=3)
    tasks = db.query(Task).filter(
        Task.user_id == user_id,
        Task.is_deleted == False,
        Task.is_completed == False,
        Task.deadline.isnot(None),
        Task.deadline >= now,
        Task.deadline <= three_days_later
    ).order_by(Task.deadline.asc()).all()
    return tasks

@app.post("/tasks")
def create_task(task: TaskCreate, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    new_task = Task(
        user_id=user_id,
        title=task.title,
        description=task.description,
        category=task.category,
        priority=task.priority,
        deadline=task.deadline
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return {"message": "Task created", "task": new_task}

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    existing_task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id, Task.is_deleted == False).first()
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.title is not None:
        existing_task.title = task.title
    if task.description is not None:
        existing_task.description = task.description
    if task.category is not None:
        existing_task.category = task.category
    if task.priority is not None:
        existing_task.priority = task.priority
    if task.deadline is not None:
        existing_task.deadline = task.deadline
    if task.is_completed is not None:
        existing_task.is_completed = task.is_completed
    
    db.commit()
    db.refresh(existing_task)
    return {"message": "Task updated", "task": existing_task}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    existing_task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id, Task.is_deleted == False).first()
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Soft delete
    existing_task.is_deleted = True
    existing_task.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "Task moved to history"}

@app.delete("/tasks/permanent/{task_id}")
def permanent_delete_task(task_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    existing_task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id, Task.is_deleted == True).first()
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found in history")
    
    db.delete(existing_task)
    db.commit()
    return {"message": "Task permanently deleted"}

@app.post("/tasks/restore/{task_id}")
def restore_task(task_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    existing_task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id, Task.is_deleted == True).first()
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found in history")
    
    existing_task.is_deleted = False
    existing_task.deleted_at = None
    db.commit()
    return {"message": "Task restored from history"}

app.mount("/", StaticFiles(directory="static", html=True), name="static")