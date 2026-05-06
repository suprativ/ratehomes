from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ratehomes_demo_secret")

DB_NAME = "ratehomes.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


USERS = {
    "screener@ratehomes.com": {"password": "screen123", "role": "screener", "name": "Screening Team"},
    "admin@ratehomes.com": {"password": "admin123", "role": "admin", "name": "Operations Admin"},
    "lo@ratehomes.com": {"password": "loan123", "role": "loan_officer", "name": "Loan Officer"},
}


AGENTS = [
    {
        "name": "Sarah Mitchell",
        "brokerage": "Compass Real Estate",
        "email": "sarah.mitchell@realty.com",
        "phone": "(312) 555-0198",
        "mls_id": "MLS-8901234",
        "license_number": "IL-475.123456",
        "brokerage_license": "IL-478.987654",
        "city": "Chicago",
        "state": "IL",
        "zip_code": "60601",
        "total_transactions": 156,
        "last_12_months": 23,
        "service_regions": "4 zip codes",
        "status": "MLS Verified",
        "screening_stage": "mls_verified",
        "interview_score": 0,
        "web_lead_score": 0,
        "lead_volume_percent": 0,
        "contact_process_score": 0,
        "lead_incubation_score": 0,
        "prequalification_score": 0,
        "willingness_to_refer_score": 0,
        "overall_assessment": "Does Not Meet Minimum Criteria",
    },
    {
        "name": "Marcus Chen",
        "brokerage": "Keller Williams",
        "email": "marcus.chen@kw.com",
        "phone": "(847) 555-0276",
        "mls_id": "MLS-8902345",
        "license_number": "IL-475.234567",
        "brokerage_license": "IL-478.234567",
        "city": "Naperville",
        "state": "IL",
        "zip_code": "60540",
        "total_transactions": 198,
        "last_12_months": 28,
        "service_regions": "4 zip codes",
        "status": "Interview Scheduled",
        "screening_stage": "interview_scheduled",
        "interview_score": 0,
        "web_lead_score": 0,
        "lead_volume_percent": 0,
        "contact_process_score": 0,
        "lead_incubation_score": 0,
        "prequalification_score": 0,
        "willingness_to_refer_score": 0,
        "overall_assessment": "Interview Pending",
    },
    {
        "name": "Jennifer Rodriguez",
        "brokerage": "RE/MAX Suburban",
        "email": "j.rodriguez@remax.com",
        "phone": "(630) 555-0384",
        "mls_id": "MLS-8903456",
        "license_number": "IL-475.345678",
        "brokerage_license": "IL-478.345678",
        "city": "Oak Brook",
        "state": "IL",
        "zip_code": "60523",
        "total_transactions": 142,
        "last_12_months": 19,
        "service_regions": "4 zip codes",
        "status": "Interview Complete",
        "screening_stage": "interview_complete",
        "interview_score": 88,
        "web_lead_score": 8,
        "lead_volume_percent": 24,
        "contact_process_score": 8,
        "lead_incubation_score": 7,
        "prequalification_score": 8,
        "willingness_to_refer_score": 9,
        "overall_assessment": "Meets Minimum Criteria",
    },
    {
        "name": "David Thompson",
        "brokerage": "Coldwell Banker",
        "email": "dthompson@cbexchange.com",
        "phone": "(773) 555-0492",
        "mls_id": "MLS-8904567",
        "license_number": "IL-475.456789",
        "brokerage_license": "IL-478.456789",
        "city": "Evanston",
        "state": "IL",
        "zip_code": "60201",
        "total_transactions": 215,
        "last_12_months": 31,
        "service_regions": "4 zip codes",
        "status": "Approved",
        "screening_stage": "approved",
        "interview_score": 92,
        "web_lead_score": 9,
        "lead_volume_percent": 31,
        "contact_process_score": 9,
        "lead_incubation_score": 8,
        "prequalification_score": 9,
        "willingness_to_refer_score": 9,
        "overall_assessment": "Approved for Agent Network",
    },
    {
        "name": "Amanda Foster",
        "brokerage": "Local Realty Group",
        "email": "afoster@localrealty.com",
        "phone": "(708) 555-0567",
        "mls_id": "MLS-8905678",
        "license_number": "IL-475.567890",
        "brokerage_license": "IL-478.567890",
        "city": "Joliet",
        "state": "IL",
        "zip_code": "60435",
        "total_transactions": 89,
        "last_12_months": 11,
        "service_regions": "3 zip codes",
        "status": "Rejected",
        "screening_stage": "rejected",
        "interview_score": 34,
        "web_lead_score": 4,
        "lead_volume_percent": 8,
        "contact_process_score": 4,
        "lead_incubation_score": 3,
        "prequalification_score": 4,
        "willingness_to_refer_score": 5,
        "overall_assessment": "Does Not Meet Minimum Criteria",
    },
]


LEADS = [
    {"name": "Robert Hill", "city": "Chicago", "state": "IL", "zip_code": "60601", "loan_type": "Purchase", "status": "New", "assigned_agent": "David Thompson"},
    {"name": "Emily Carter", "city": "Naperville", "state": "IL", "zip_code": "60540", "loan_type": "Refinance", "status": "Contacted", "assigned_agent": ""},
]


def login_required(role=None):
    def wrapper(fn):
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Access denied for this role.")
                return redirect(url_for("home"))
            return fn(*args, **kwargs)
        decorated.__name__ = fn.__name__
        return decorated
    return wrapper


def count_by_status(status):
    return len([a for a in AGENTS if a["status"] == status])


def passed_criteria(agent):
    checks = [
        agent["last_12_months"] >= 15,
        agent["web_lead_score"] >= 7,
        agent["lead_volume_percent"] >= 20,
        agent["contact_process_score"] >= 7,
        agent["lead_incubation_score"] >= 7,
        agent["prequalification_score"] >= 7,
        agent["willingness_to_refer_score"] >= 8,
    ]
    return sum(checks)


@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    if session["role"] == "screener":
        return redirect(url_for("screening"))
    if session["role"] == "admin":
        return redirect(url_for("management"))
    if session["role"] == "loan_officer":
        return redirect(url_for("sales"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = USERS.get(email)
        if user and user["password"] == password:
            session["user"] = email
            session["role"] = user["role"]
            session["name"] = user["name"]
            return redirect(url_for("home"))

        flash("Invalid email or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/screening")
@login_required("screener")
def screening():
    selected_id = int(request.args.get("id", 0))
    selected_agent = AGENTS[selected_id] if selected_id < len(AGENTS) else AGENTS[0]

    stats = {
        "total_agents": len(AGENTS),
        "mls_verified": count_by_status("MLS Verified"),
        "interview_scheduled": count_by_status("Interview Scheduled"),
        "interview_complete": count_by_status("Interview Complete"),
        "approved": count_by_status("Approved"),
        "rejected": count_by_status("Rejected"),
    }

    return render_template(
        "screening.html",
        agents=AGENTS,
        selected_agent=selected_agent,
        selected_id=selected_id,
        stats=stats,
        passed_criteria=passed_criteria(selected_agent),
        user_name=session.get("name"),
    )


@app.route("/screening/action/<int:agent_id>/<action>", methods=["POST"])
@login_required("screener")
def screening_action(agent_id, action):
    if 0 <= agent_id < len(AGENTS):
        if action == "schedule":
            AGENTS[agent_id]["status"] = "Interview Scheduled"
        elif action == "complete":
            AGENTS[agent_id]["status"] = "Interview Complete"
            AGENTS[agent_id]["interview_score"] = 88
        elif action == "approve":
            AGENTS[agent_id]["status"] = "Pending Admin Approval"
        elif action == "reject":
            AGENTS[agent_id]["status"] = "Rejected"
    return redirect(url_for("screening", id=agent_id))


@app.route("/management")
@login_required("admin")
def management():
    pending = [a for a in AGENTS if a["status"] in ["Pending Admin Approval", "Interview Complete"]]
    approved = [a for a in AGENTS if a["status"] == "Approved"]
    rejected = [a for a in AGENTS if a["status"] == "Rejected"]

    return render_template(
        "management.html",
        agents=AGENTS,
        pending=pending,
        approved=approved,
        rejected=rejected,
        user_name=session.get("name"),
    )


@app.route("/management/action/<int:agent_id>/<action>", methods=["POST"])
@login_required("admin")
def management_action(agent_id, action):
    if 0 <= agent_id < len(AGENTS):
        if action == "approve":
            AGENTS[agent_id]["status"] = "Approved"
        elif action == "reject":
            AGENTS[agent_id]["status"] = "Rejected"
        elif action == "deactivate":
            AGENTS[agent_id]["status"] = "Inactive"
        elif action == "suspend":
            AGENTS[agent_id]["status"] = "Suspended"
    return redirect(url_for("management"))


@app.route("/sales")
@login_required("loan_officer")
def sales():
    approved_agents = [a for a in AGENTS if a["status"] == "Approved"]
    return render_template(
        "sales.html",
        leads=LEADS,
        approved_agents=approved_agents,
        user_name=session.get("name"),
    )


@app.route("/borrower-search")
def borrower_search():
    query = request.args.get("q", "").lower().strip()
    approved_agents = [a for a in AGENTS if a["status"] == "Approved"]

    if query:
        approved_agents = [
            a for a in approved_agents
            if query in a["city"].lower()
            or query in a["state"].lower()
            or query in a["zip_code"].lower()
        ]

    return render_template("borrower_search.html", agents=approved_agents, query=query)


@app.route("/agent-onboarding", methods=["GET", "POST"])
def agent_onboarding():
    if request.method == "POST":
        new_agent = {
            "name": request.form.get("name", "New Agent"),
            "brokerage": request.form.get("brokerage", ""),
            "email": request.form.get("email", ""),
            "phone": request.form.get("phone", ""),
            "mls_id": request.form.get("mls_id", ""),
            "license_number": request.form.get("license_number", ""),
            "brokerage_license": request.form.get("brokerage_license", ""),
            "city": request.form.get("city", ""),
            "state": request.form.get("state", ""),
            "zip_code": request.form.get("zip_code", ""),
            "total_transactions": int(request.form.get("total_transactions", 0) or 0),
            "last_12_months": int(request.form.get("last_12_months", 0) or 0),
            "service_regions": request.form.get("service_regions", "Not provided"),
            "status": "MLS Verified",
            "screening_stage": "mls_verified",
            "interview_score": 0,
            "web_lead_score": 0,
            "lead_volume_percent": 0,
            "contact_process_score": 0,
            "lead_incubation_score": 0,
            "prequalification_score": 0,
            "willingness_to_refer_score": 0,
            "overall_assessment": "Pending Screening",
        }
        AGENTS.insert(0, new_agent)
        flash("Agent profile submitted successfully.")
        return redirect(url_for("login"))

    return render_template("agent_onboarding.html")


@app.route("/api-flow")
@login_required()
def api_flow():
    return render_template("api_flow.html", user_name=session.get("name"))


if __name__ == "__main__":
    app.run(debug=True)
