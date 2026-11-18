def test_login_and_me(client, users, auth):
    r = client.get("/api/auth/me", headers=auth("officer"))
    assert r.status_code == 200
    assert r.json()["role"] == "safety_officer"


def test_login_wrong_password(client, users):
    r = client.post("/api/auth/login", json={"email": "officer@test.in", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_is_case_insensitive(client, users):
    r = client.post("/api/auth/login", json={"email": "OFFICER@test.in", "password": "Password@123"})
    assert r.status_code == 200


def test_no_token_is_401(client):
    assert client.get("/api/incidents").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_inactive_user_cannot_log_in(client, users, db):
    u = db.merge(users["reporter2"])
    u.is_active = False
    db.commit()
    r = client.post("/api/auth/login", json={"email": "reporter2@test.in", "password": "Password@123"})
    assert r.status_code == 401


def test_reporter_cannot_do_officer_actions(client, auth, make_incident):
    inc = make_incident()
    h = auth("reporter")
    assert client.post(f"/api/incidents/{inc['id']}/start-review", headers=h).status_code == 403
    assert client.get("/api/admin/incidents", headers=h).status_code == 403
    assert client.get("/api/dashboard/stats", headers=h).status_code == 403


def test_admin_is_read_only_on_workflow(client, auth, make_incident):
    inc = make_incident()
    assert client.post(f"/api/incidents/{inc['id']}/start-review", headers=auth("admin")).status_code == 403
    assert client.get(f"/api/incidents/{inc['id']}", headers=auth("admin")).status_code == 200


def test_officer_cannot_manage_users(client, auth):
    assert client.get("/api/admin/users", headers=auth("officer")).status_code == 403


def test_reporter_sees_only_own_incidents(client, auth, make_incident):
    inc = make_incident()
    other = auth("reporter2")
    assert client.get(f"/api/incidents/{inc['id']}", headers=other).status_code == 404
    assert client.get("/api/incidents", headers=other).json()["total"] == 0
    assert client.get("/api/incidents", headers=auth("reporter")).json()["total"] == 1
    assert client.get("/api/incidents", headers=auth("officer")).json()["total"] == 1


def test_admin_creates_user(client, auth):
    body = {"email": "new.officer@test.in", "full_name": "New Officer", "password": "Str0ngPass!", "role": "safety_officer"}
    r = client.post("/api/admin/users", json=body, headers=auth("admin"))
    assert r.status_code == 201
    assert client.post("/api/admin/users", json=body, headers=auth("admin")).status_code == 409
    login = client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})
    assert login.status_code == 200
