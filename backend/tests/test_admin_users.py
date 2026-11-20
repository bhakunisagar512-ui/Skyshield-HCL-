PW = "Password@123"


def login(client, email, password=PW):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_deactivate_blocks_login_and_existing_token(client, auth, users):
    reporter_headers = auth("reporter")
    rid = users["reporter"].id
    r = client.patch(f"/api/admin/users/{rid}", json={"is_active": False}, headers=auth("admin"))
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert login(client, "reporter@test.in").status_code == 401
    assert client.get("/api/auth/me", headers=reporter_headers).status_code == 401
    # reactivate
    assert client.patch(f"/api/admin/users/{rid}", json={"is_active": True}, headers=auth("admin")).status_code == 200
    assert login(client, "reporter@test.in").status_code == 200


def test_deactivated_users_records_are_kept(client, auth, users, make_incident):
    inc = make_incident()
    client.patch(f"/api/admin/users/{users['reporter'].id}", json={"is_active": False}, headers=auth("admin"))
    detail = client.get(f"/api/incidents/{inc['id']}", headers=auth("officer")).json()
    assert detail["reporter"]["full_name"] == "Reporter"


def test_role_change_applies_immediately(client, auth, users):
    reporter_headers = auth("reporter")
    assert client.get("/api/dashboard/stats", headers=reporter_headers).status_code == 403
    r = client.patch(f"/api/admin/users/{users['reporter'].id}", json={"role": "safety_officer"}, headers=auth("admin"))
    assert r.json()["role"] == "safety_officer"
    # same token, new permissions: role is read from the database on every request
    assert client.get("/api/dashboard/stats", headers=reporter_headers).status_code == 200


def test_admin_cannot_lock_themselves_out(client, auth, users):
    aid = users["admin"].id
    h = auth("admin")
    assert client.patch(f"/api/admin/users/{aid}", json={"is_active": False}, headers=h).status_code == 409
    assert client.patch(f"/api/admin/users/{aid}", json={"role": "reporter"}, headers=h).status_code == 409
    assert client.patch(f"/api/admin/users/{aid}", json={"full_name": "Chief Admin"}, headers=h).json()["full_name"] == "Chief Admin"


def test_last_active_admin_is_protected(client, auth, users):
    h = auth("admin")
    second = client.post("/api/admin/users", headers=h, json={
        "email": "admin2@test.in", "full_name": "Second Admin", "password": "Str0ngPass!", "role": "admin"}).json()
    # with two admins, the second may be deactivated
    assert client.patch(f"/api/admin/users/{second['id']}", json={"is_active": False}, headers=h).status_code == 200
    # make the first admin's own demotion impossible via the second, now inactive, admin: still blocked
    client.patch(f"/api/admin/users/{second['id']}", json={"is_active": True}, headers=h)
    h2 = {"Authorization": "Bearer " + login(client, "admin2@test.in", "Str0ngPass!").json()["access_token"]}
    assert client.patch(f"/api/admin/users/{users['admin'].id}", json={"is_active": False}, headers=h2).status_code == 200
    # now admin2 is the only active admin and cannot be removed by anyone
    assert client.patch(f"/api/admin/users/{second['id']}", json={"role": "reporter"}, headers=h2).status_code == 409


def test_reset_password(client, auth, users):
    oid = users["officer"].id
    assert client.post(f"/api/admin/users/{oid}/reset-password", json={"password": "short"},
                       headers=auth("admin")).status_code == 422
    assert client.post(f"/api/admin/users/{oid}/reset-password", json={"password": "NewPass#2026"},
                       headers=auth("admin")).status_code == 204
    assert login(client, "officer@test.in").status_code == 401
    assert login(client, "officer@test.in", "NewPass#2026").status_code == 200


def test_only_admin_can_manage_users(client, auth, users):
    uid = users["reporter"].id
    for who in ("officer", "reporter"):
        assert client.patch(f"/api/admin/users/{uid}", json={"is_active": False}, headers=auth(who)).status_code == 403
        assert client.post(f"/api/admin/users/{uid}/reset-password", json={"password": "Whatever#123"},
                           headers=auth(who)).status_code == 403
    assert client.patch("/api/admin/users/99999", json={"is_active": False}, headers=auth("admin")).status_code == 404
