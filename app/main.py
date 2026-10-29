"""Edwards Technology & Operations: public website and inquiry management."""
import os
import re
import sqlite3
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", "/data/agency.db"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "hello@example.com")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Edwards Technology & Operations")
security = HTTPBasic(auto_error=False)
app = FastAPI(title=BUSINESS_NAME, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            company TEXT NOT NULL,
            service TEXT NOT NULL,
            message TEXT NOT NULL
        )""")

@contextmanager
def database():
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        yield db

@app.on_event("startup")
def startup():
    init_db()


def context(request: Request, **extra):
    return {"request": request, "business_name": BUSINESS_NAME,
            "business_email": BUSINESS_EMAIL, **extra}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse("index.html", context(request))

@app.post("/inquiry", response_class=HTMLResponse)
def inquiry(request: Request,
            name: Annotated[str, Form(min_length=2, max_length=100)],
            email: Annotated[str, Form(max_length=150)],
            company: Annotated[str, Form(max_length=120)] = "",
            service: Annotated[str, Form(max_length=80)] = "Other",
            message: Annotated[str, Form(min_length=10, max_length=2000)] = "",
            website: Annotated[str, Form(max_length=200)] = ""):
    # Honeypot field: decline submissions filled by simple bots.
    if website:
        return templates.TemplateResponse("thanks.html", context(request))
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if service not in {"Website Development", "Business Automation", "Linux & Cloud", "Operations Consulting", "Other"}:
        raise HTTPException(status_code=422, detail="Invalid service.")
    with database() as db:
        db.execute("INSERT INTO inquiries (created_at,name,email,company,service,message) VALUES (?,?,?,?,?,?)",
                   (datetime.now(timezone.utc).isoformat(), name.strip(), email,
                    company.strip(), service, message.strip()))
        db.commit()
    return templates.TemplateResponse("thanks.html", context(request))


def authenticate(credentials: HTTPBasicCredentials | None = Depends(security)):
    # Refuse admin access until a real secret is configured.
    if not ADMIN_PASSWORD or not credentials or not (
        secrets.compare_digest(credentials.username.encode(), ADMIN_USERNAME.encode()) and
        secrets.compare_digest(credentials.password.encode(), ADMIN_PASSWORD.encode())
    ):
        raise HTTPException(status_code=401, detail="Authentication required",
                            headers={"WWW-Authenticate": 'Basic realm="Agency Admin"'})

@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(authenticate)])
def admin(request: Request):
    with database() as db:
        items = db.execute("SELECT * FROM inquiries ORDER BY id DESC LIMIT 500").fetchall()
    return templates.TemplateResponse("admin.html", context(request, inquiries=items))
