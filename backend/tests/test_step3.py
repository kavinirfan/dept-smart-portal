from datetime import date, timedelta

from app.seed import DEMO_PASSWORD


def auth(client, email):
    r = client.post("/api/auth/login", data={"username": email, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def token(client, email):
    return auth(client, email)["Authorization"].split()[1]


def me(client, email):
    return client.get("/api/auth/me", headers=auth(client, email)).json()


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


# ---- Notifications --------------------------------------------------------------

def test_marks_save_notifies_student(client):
    h = auth(client, "lakshmi@dept.edu")
    subj = client.get("/api/marks/my-subjects", headers=h).json()[0]
    comp = client.post("/api/marks/components", headers=h, json={
        "subject_id": subj["subject_id"], "name": "Lab test", "question_max": [10], "weightage": 5}).json()
    gayathri = me(client, "gayathri@dept.edu")
    client.put(f"/api/marks/sheet/{comp['component_id']}", headers=h, json=[{"student_id": gayathri["user_id"], "question_marks": [8]}])
    inbox = client.get("/api/notifications", headers=auth(client, "gayathri@dept.edu")).json()
    assert inbox["unread"] >= 1 and "Lab test marks updated: 8/10" in inbox["items"][0]["message"]
    client.post("/api/notifications/read-all", headers=auth(client, "gayathri@dept.edu"))
    assert client.get("/api/notifications", headers=auth(client, "gayathri@dept.edu")).json()["unread"] == 0


def test_new_notice_notifies_others_not_poster(client):
    h = auth(client, "priya@dept.edu")
    client.post("/api/notices", headers=h, json={"title": "Design intern", "company": "Acme", "description": "x", "type": "internship",
                                                 "deadline": (date.today() + timedelta(days=9)).isoformat()})
    assert "Design intern" in client.get("/api/notifications", headers=auth(client, "aditya@dept.edu")).json()["items"][0]["message"]
    assert all("Design intern" not in n["message"] for n in client.get("/api/notifications", headers=h).json()["items"])


def test_cancel_by_incharge_notifies_booker(client):
    lab = client.get("/api/labs", headers=auth(client, "rahul@dept.edu")).json()[0]["lab_id"]
    day = (date.today() + timedelta(days=5)).isoformat()
    b = client.post("/api/labs/bookings", headers=auth(client, "rahul@dept.edu"),
                    json={"lab_id": lab, "start_time": f"{day}T09:00", "end_time": f"{day}T10:00", "purpose": "Viva"}).json()
    assert any("booked" in n["message"] for n in client.get("/api/notifications", headers=auth(client, "labincharge@dept.edu")).json()["items"])
    client.delete(f"/api/labs/bookings/{b['booking_id']}", headers=auth(client, "labincharge@dept.edu"))
    assert "cancelled your" in client.get("/api/notifications", headers=auth(client, "rahul@dept.edu")).json()["items"][0]["message"]


# ---- Dashboard ------------------------------------------------------------------

def test_dashboard_admin_only(client):
    assert client.get("/api/dashboard", headers=auth(client, "arjun@dept.edu")).status_code == 403
    d = client.get("/api/dashboard", headers=auth(client, "hod@dept.edu")).json()
    assert d["people"]["student"] == 6 and len(d["labs"]) == 3 and len(d["subjects"]) == 4
    assert d["chat"]["pending_ids"] == 1 and d["chat"]["reported"] == 1


# ---- Chat -----------------------------------------------------------------------

def test_unverified_student_cannot_unlock(client):
    h = auth(client, "gayathri@dept.edu")
    assert client.post("/api/chat/unlock/password", headers=h, json={"password": DEMO_PASSWORD}).status_code == 403
    assert client.get("/api/chat/messages", headers=h).status_code == 403


def test_id_card_flow_then_chat(client):
    h = auth(client, "gayathri@dept.edu")
    bad = client.post("/api/chat/id-card", headers=h, data={"id_number": "21CS006"}, files={"image": ("id.txt", b"hi", "text/plain")})
    assert bad.status_code == 422
    reg = client.post("/api/chat/id-card", headers=h, data={"id_number": "21CS006"}, files={"image": ("id.png", PNG, "image/png")}).json()
    admin = auth(client, "hod@dept.edu")
    assert any(r["registration_id"] == reg["registration_id"] for r in client.get("/api/chat/id-cards", headers=admin).json())
    assert client.get(f"/api/chat/id-cards/{reg['registration_id']}/image", headers=admin).content == PNG
    assert client.get(f"/api/chat/id-cards/{reg['registration_id']}/image", headers=auth(client, "kavin@dept.edu")).status_code == 404
    assert client.post(f"/api/chat/id-cards/{reg['registration_id']}/review", headers=admin, json={"approve": False}).status_code == 422
    assert client.post(f"/api/chat/id-cards/{reg['registration_id']}/review", headers=admin, json={"approve": True}).status_code == 200
    assert client.post("/api/chat/unlock/password", headers=h, json={"password": "wrong"}).status_code == 400
    assert client.post("/api/chat/unlock/password", headers=h, json={"password": DEMO_PASSWORD}).status_code == 200
    assert client.get("/api/chat/status", headers=h).json()["session_expires"] is not None

    # Kavin unlocks too; a message from Gayathri reaches Kavin's socket in real time.
    client.post("/api/chat/unlock/password", headers=auth(client, "kavin@dept.edu"), json={"password": DEMO_PASSWORD})
    with client.websocket_connect(f"/api/chat/ws?token={token(client, 'kavin@dept.edu')}") as kws, \
            client.websocket_connect(f"/api/chat/ws?token={token(client, 'gayathri@dept.edu')}") as gws:
        gws.send_json({"text": "Hello campus!"})
        got = None
        for _ in range(6):
            evt = kws.receive_json()
            if evt["type"] == "message":
                got = evt
                break
        assert got and got["text"] == "Hello campus!" and got["sender_name"] == "Gayathri K"

    hist = client.get("/api/chat/messages", headers=h).json()
    assert hist[-1]["text"] == "Hello campus!"


def test_socket_rejected_without_session(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/chat/ws?token={token(client, 'aditya@dept.edu')}") as ws:
            ws.receive_json()


def test_report_and_moderate(client):
    admin = auth(client, "hod@dept.edu")
    client.post("/api/chat/unlock/password", headers=admin, json={"password": DEMO_PASSWORD})
    flagged = client.get("/api/chat/reported", headers=admin).json()
    assert len(flagged) == 1
    mid = flagged[0]["message_id"]
    assert client.post(f"/api/chat/messages/{mid}/moderate", headers=auth(client, "kavin@dept.edu"), json={"hide": True}).status_code == 403
    assert client.post(f"/api/chat/messages/{mid}/moderate", headers=admin, json={"hide": True}).json()["hidden"] is True
    assert all(m["message_id"] != mid for m in client.get("/api/chat/messages", headers=admin).json())


def test_webauthn_needs_allowed_origin(client):
    h = auth(client, "kavin@dept.edu")
    r = client.post("/api/chat/webauthn/register/options", headers={**h, "Origin": "http://evil.example"})
    assert r.status_code == 400
    ok = client.post("/api/chat/webauthn/register/options", headers={**h, "Origin": "http://localhost:8000"})
    assert ok.status_code == 200 and ok.json()["rp"]["id"] == "localhost"
