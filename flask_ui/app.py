"""Simple Flask demo UI. Calls FastAPI. No React."""

from __future__ import annotations

from pathlib import Path

import httpx
from flask import Flask, flash, redirect, render_template, request, session, url_for

from app.config import get_settings

ROLES = [
    {"role": "EMPLOYEE", "name": "Rahul Sharma", "employee_id": "EMP-1001"},
    {"role": "MANAGER", "name": "Neha Rao", "employee_id": "MGR-01"},
    {"role": "BU_HEAD", "name": "Arjun Menon", "employee_id": "BU-01"},
    {"role": "CFO", "name": "Priya Sen", "employee_id": "CFO-01"},
    {"role": "FINANCE", "name": "Karan Mehta", "employee_id": "FIN-01"},
    {"role": "ADMIN", "name": "Admin", "employee_id": "ADM-01"},
]


def create_app() -> Flask:
    root = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    DEFAULT_GRAPH = [
        {"id": "upload", "label": "Upload", "kind": "input", "status": "completed", "detail": "Receipts", "selected": False},
        {"id": "extract", "label": "Understand", "kind": "ai", "status": "completed", "detail": "Extract JSON", "selected": False},
        {"id": "validate", "label": "Validate", "kind": "tool", "status": "completed", "detail": "Guardrails", "selected": False},
        {"id": "policy", "label": "Policy", "kind": "code", "status": "completed", "detail": "CFO", "selected": False},
        {"id": "approval", "label": "Human", "kind": "human", "status": "running", "detail": "Authorize", "selected": True},
        {"id": "payment", "label": "Payment", "kind": "act", "status": "pending", "detail": "Reimburse", "selected": False},
    ]
    settings = get_settings()
    app.secret_key = settings.secret_key
    api = settings.api_base_url.rstrip("/")

    def actor_headers() -> dict[str, str]:
        return {
            "X-Role": session.get("role", "EMPLOYEE"),
            "X-User": session.get("name", "Rahul Sharma"),
            "X-Employee-Id": session.get("employee_id", "EMP-1001"),
        }

    def api_get(path: str) -> dict | list:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{api}{path}", headers=actor_headers())
            r.raise_for_status()
            return r.json()

    def api_post(path: str, **kwargs) -> dict:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{api}{path}", headers=actor_headers(), **kwargs)
            if r.status_code >= 400:
                detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text
                raise RuntimeError(str(detail))
            return r.json()

    @app.context_processor
    def inject() -> dict:
        demo = True
        try:
            health = api_get("/health")
            demo = bool(health.get("demo_mode", True))
        except Exception:
            demo = True
        return {
            "roles": ROLES,
            "current_role": session.get("role", "EMPLOYEE"),
            "current_name": session.get("name", "Rahul Sharma"),
            "demo_mode": demo,
        }

    @app.route("/switch-role", methods=["POST"])
    def switch_role():
        role = request.form.get("role", "EMPLOYEE")
        match = next((r for r in ROLES if r["role"] == role), ROLES[0])
        session["role"] = match["role"]
        session["name"] = match["name"]
        session["employee_id"] = match["employee_id"]
        return redirect(request.referrer or url_for("dashboard"))

    @app.route("/")
    def dashboard():
        try:
            data = api_get("/dashboard")
        except Exception as exc:
            return render_template("error.html", message=f"API not reachable: {exc}")
        return render_template("dashboard.html", data=data, graph=DEFAULT_GRAPH)

    @app.route("/claims/new", methods=["GET", "POST"])
    def new_claim():
        if request.method == "POST":
            files = []
            for f in request.files.getlist("files"):
                if f and f.filename:
                    files.append(("files", (f.filename, f.stream, f.mimetype or "application/octet-stream")))
            data = {
                "employee_name": request.form.get("employee_name", ""),
                "employee_id": request.form.get("employee_id", ""),
                "trip_purpose": request.form.get("trip_purpose", ""),
                "trip_location": request.form.get("trip_location", ""),
                "trip_start": request.form.get("trip_start", ""),
                "trip_end": request.form.get("trip_end", ""),
            }
            try:
                created = api_post("/claims", data=data, files=files or None)
                claim_id = created["claim_id"]
                api_post(f"/claims/{claim_id}/process")
                return redirect(url_for("claim_detail", claim_id=claim_id))
            except Exception as exc:
                flash(str(exc), "error")
        return render_template("new_claim.html")

    @app.route("/claims/<claim_id>")
    def claim_detail(claim_id: str):
        try:
            claim = api_get(f"/claims/{claim_id}")
        except Exception as exc:
            return render_template("error.html", message=str(exc))
        return render_template("claim.html", claim=claim)

    @app.route("/claims/<claim_id>/approve", methods=["POST"])
    def approve(claim_id: str):
        try:
            api_post(f"/claims/{claim_id}/approve")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    @app.route("/claims/<claim_id>/reject", methods=["POST"])
    def reject(claim_id: str):
        try:
            api_post(f"/claims/{claim_id}/reject")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    @app.route("/claims/<claim_id>/retry-payment", methods=["POST"])
    def retry_payment(claim_id: str):
        try:
            api_post(f"/claims/{claim_id}/retry-payment")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    @app.route("/claims/<claim_id>/trace")
    def trace(claim_id: str):
        try:
            data = api_get(f"/claims/{claim_id}/trace")
        except Exception as exc:
            return render_template("error.html", message=str(exc))
        return render_template("trace.html", data=data)

    @app.route("/approvals")
    def approvals():
        try:
            rows = api_get("/approvals")
        except Exception as exc:
            return render_template("error.html", message=str(exc))
        return render_template("approvals.html", rows=rows)

    @app.route("/policies", methods=["GET", "POST"])
    def policies():
        if request.method == "POST":
            version = request.form.get("version", "v1")
            action = request.form.get("action", "activate")
            try:
                api_post("/policies/activate", json={"version": version, "action": action})
                flash(f"Policy {action}: {version}", "ok")
            except Exception as exc:
                flash(str(exc), "error")
            return redirect(url_for("policies"))
        try:
            data = api_get("/policies")
        except Exception as exc:
            return render_template("error.html", message=str(exc))
        return render_template("policies.html", data=data)

    @app.route("/evaluation")
    def evaluation():
        try:
            data = api_get("/evaluation")
        except Exception as exc:
            return render_template("error.html", message=str(exc))
        return render_template("evaluation.html", data=data)

    @app.route("/demo")
    def demo():
        return render_template("demo.html")

    @app.route("/demo/run/<scenario>", methods=["POST"])
    def demo_run(scenario: str):
        paths = {
            "duplicate": "/demo/duplicate",
            "payment": "/demo/failure/payment",
            "circuit": "/demo/failure/circuit",
            "loop": "/demo/failure/loop",
            "injection": "/demo/prompt-injection",
        }
        path = paths.get(scenario)
        if not path:
            flash("Unknown scenario", "error")
            return redirect(url_for("demo"))
        try:
            result = api_post(path)
        except Exception as exc:
            flash(str(exc), "error")
            return redirect(url_for("demo"))
        if scenario == "duplicate":
            session["dup_first"] = result["first"]["claim_id"]
            return redirect(url_for("claim_detail", claim_id=result["second"]["claim_id"]))
        return redirect(url_for("claim_detail", claim_id=result["claim_id"]))

    return app


if __name__ == "__main__":
    settings = get_settings()
    create_app().run(host=settings.flask_host, port=settings.flask_port, debug=True)
