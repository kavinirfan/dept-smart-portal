from app.seed import DEMO_PASSWORD


def login(client, email):
    r = client.post("/api/auth/login", data={"username": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_login_and_me(client):
    h = login(client, "kavin@dept.edu")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "student" and me["roll_no"] == "21CS001"


def test_wrong_password(client):
    r = client.post("/api/auth/login", data={"username": "kavin@dept.edu", "password": "nope"})
    assert r.status_code == 401


def test_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_student_cannot_list_users(client):
    assert client.get("/api/users", headers=login(client, "kavin@dept.edu")).status_code == 403


def test_admin_creates_user_and_it_is_audited(client):
    h = login(client, "hod@dept.edu")
    r = client.post("/api/users", headers=h, json={
        "name": "New Student", "email": "new@dept.edu", "password": "secret1", "role": "student", "roll_no": "21CS099",
    })
    assert r.status_code == 201, r.text
    dup = client.post("/api/users", headers=h, json={
        "name": "Dup", "email": "new@dept.edu", "password": "secret1", "role": "student", "roll_no": "21CS100",
    })
    assert dup.status_code == 409
    log = client.get("/api/audit", headers=h).json()
    assert log[0]["action"] == "create" and "new@dept.edu" in log[0]["details"]


def test_teacher_cannot_create_user(client):
    h = login(client, "arjun@dept.edu")
    r = client.post("/api/users", headers=h, json={
        "name": "X", "email": "x@dept.edu", "password": "secret1", "role": "admin",
    })
    assert r.status_code == 403


def test_credentials_scoped_to_teacher(client):
    creds = client.get("/api/credentials", headers=login(client, "arjun@dept.edu")).json()
    assert sorted(c["subject"]["subject_code"] for c in creds) == ["CS501", "CS504"]


def test_credential_only_for_teachers(client):
    h = login(client, "hod@dept.edu")
    r = client.post("/api/credentials", headers=h, json={"user_id": 6, "subject_id": 1})
    assert r.status_code == 422


def test_admin_cannot_deactivate_self(client):
    h = login(client, "hod@dept.edu")
    r = client.patch("/api/users/1", headers=h, json={"is_active": False})
    assert r.status_code == 400
