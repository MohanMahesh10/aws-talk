"""HTTP-level happy path, approval, demos."""

HEADERS = {"X-Role": "EMPLOYEE", "X-User": "Rahul Sharma", "X-Employee-Id": "EMP-1001"}
CFO = {"X-Role": "CFO", "X-User": "Priya Sen", "X-Employee-Id": "CFO-01"}
ADMIN = {"X-Role": "ADMIN", "X-User": "Admin", "X-Employee-Id": "ADM-01"}


def test_health_demo_mode(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["demo_mode"] is True


def test_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_seed_talk_claim(client):
    r = client.get("/claims/CLM-1001", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total_amount"] == 24550
    assert body["required_approver"] == "CFO"
    assert body["state"] == "APPROVAL_REQUIRED"


def test_claim_a_b_c(client):
    hidden = client.get("/claims/CLM-A", headers=HEADERS)
    assert hidden.status_code == 403

    mgr = {"X-Role": "MANAGER", "X-User": "Neha", "X-Employee-Id": "MGR-01"}
    a = client.get("/claims/CLM-A", headers=mgr).json()
    b = client.get("/claims/CLM-B", headers=mgr).json()
    c = client.get("/claims/CLM-C", headers=mgr).json()
    assert a["required_approver"] == "MANAGER"
    assert b["required_approver"] == "CFO"
    assert c["required_approver"] == "CFO + Finance"


def test_approve_then_pay(client):
    r = client.post("/claims/CLM-1001/approve", headers=CFO)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "COMPLETED"
    assert body["payment_status"] == "success"


def test_employee_cannot_approve(client):
    r = client.post("/claims/CLM-B/approve", headers=HEADERS)
    assert r.status_code == 403


def test_duplicate_demo(client):
    r = client.post("/demo/duplicate", headers=HEADERS)
    assert r.status_code == 200
    second = r.json()["second"]
    assert second["duplicate_blocked"] is True
    assert second["state"] == "EXCEPTION"


def test_payment_retry_demo(client):
    r = client.post("/demo/failure/payment", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "COMPLETED"
    assert body["retry_count"] >= 2
    assert any(p["status"] == "failed" for p in body["payments"])
    assert any(p["status"] == "success" for p in body["payments"])


def test_circuit_demo(client):
    r = client.post("/demo/failure/circuit", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "EXCEPTION"
    assert body["circuit_open"] is True


def test_loop_demo(client):
    r = client.post("/demo/failure/loop", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["loop_detected"] is True
    assert body["state"] == "EXCEPTION"


def test_injection_demo(client):
    r = client.post("/demo/prompt-injection", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["injection_detected"] is True
    assert body["required_approver"] == "CFO"
    assert body["state"] == "APPROVAL_REQUIRED"


def test_policy_activate_admin_only(client):
    deny = client.post("/policies/activate", json={"version": "v2"}, headers=HEADERS)
    assert deny.status_code == 403
    ok = client.post("/policies/activate", json={"version": "v2", "action": "activate"}, headers=ADMIN)
    assert ok.status_code == 200
    active = [p for p in ok.json()["policies"] if p["active"]]
    assert active[0]["version"] == "v2"
