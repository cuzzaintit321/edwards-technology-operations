import os
from pathlib import Path
from fastapi.testclient import TestClient
from app import main

def test_site_and_inquiry(tmp_path):
    main.DB_PATH = tmp_path / "leads.db"
    main.init_db()
    client = TestClient(main.app)
    assert client.get("/").status_code == 200
    assert "Less busywork" in client.get("/").text
    assert client.get("/health").json() == {"status": "ok"}
    payload = {"name": "Test Customer", "email": "test@example.com", "company": "Example",
               "service": "Business Automation", "message": "Please automate our monthly reports."}
    assert client.post("/inquiry", data=payload).status_code == 200
    with main.database() as db:
        assert db.execute("SELECT count(*) FROM inquiries").fetchone()[0] == 1
    assert client.get("/admin").status_code == 401
    main.ADMIN_PASSWORD = "test-only-pass"
    assert client.get("/admin", auth=("admin", "test-only-pass")).status_code == 200
