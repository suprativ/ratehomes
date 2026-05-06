import os, sqlite3, json, datetime
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

try:
    import pandas as pd
except Exception:
    pd = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()
BASE = Path(__file__).resolve().parent
DB = BASE / "agent_network.db"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "rate-homes-local-demo-secret")

USERS = {
    "screener@ratehomes.com": {"password": "screen123", "role": "screener", "name": "Screening Team"},
    "admin@ratehomes.com": {"password": "admin123", "role": "admin", "name": "Operations Admin"},
    "lo@ratehomes.com": {"password": "loan123", "role": "loan_officer", "name": "Loan Officer"},
}

def conn():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def init_db():
    con = conn(); c = con.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS agents(
        id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT, email TEXT, phone TEXT, nmls_id TEXT,
        city TEXT, state TEXT, zip_code TEXT, market TEXT, experience_years INTEGER, monthly_volume INTEGER,
        avg_close_days INTEGER, languages TEXT, specialties TEXT, availability TEXT, bio TEXT,
        score INTEGER DEFAULT 0, ai_summary TEXT, ai_strengths TEXT, ai_risks TEXT, ai_recommendation TEXT,
        status TEXT DEFAULT 'Submitted', screener_notes TEXT, admin_notes TEXT, created_at TEXT, updated_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads(
        id INTEGER PRIMARY KEY AUTOINCREMENT, borrower_name TEXT, email TEXT, phone TEXT, city TEXT, state TEXT,
        zip_code TEXT, loan_type TEXT, lead_source TEXT, lead_status TEXT, assigned_agent_id INTEGER, last_contact_date TEXT, notes TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, agent_id INTEGER, channel TEXT, summary TEXT, created_at TEXT
    )''')
    if c.execute("SELECT COUNT(*) FROM agents").fetchone()[0] == 0:
        demo_agents = [
            ("Michael Rodriguez","mrodriguez@email.com","(708) 555-0190","NMLS-553821","Oak Park","IL","60302","Chicago West",2,4,51,"English, Spanish","First-time buyers, FHA, Condo","Weekdays 9 AM - 6 PM","Community-focused agent profile with first-time buyer exposure. Requires operational review due to lower recent volume and longer close cycle.",58,"Needs Manual Review","Submitted"),
            ("Sarah Chen","schen@email.com","(630) 555-0142","NMLS-2074481","Naperville","IL","60540","Chicago West",7,13,32,"English, Mandarin","Purchase loans, Jumbo, Relocation","7 days / fast response","High-performing referral partner with strong borrower follow-up, strong close velocity and multilingual coverage.",91,"Recommended for Admin Approval","Submitted"),
            ("Amanda Wright","awright@email.com","(217) 555-0166","NMLS-1182047","Lincoln Park","IL","60614","Chicago North",5,9,38,"English","Conventional, VA, Move-up buyers","Weekdays + Saturday","Stable production profile with solid market coverage and acceptable close cycle.",84,"Recommended for Admin Approval","Submitted"),
            ("Suprativ Das","sdas@email.com","(212) 555-0111","NMLS-123454","New York","NY","10001","New York Metro",3,5,48,"English, Hindi","Refinance, First-time buyers","Weekdays","Profile requires review due to moderate volume and incomplete recent borrower feedback.",67,"Needs Manual Review","Needs Review"),
            ("Elena Martinez","emartinez@email.com","(512) 555-0155","NMLS-662944","Austin","TX","78701","Austin Central",9,17,29,"English, Spanish","New construction, Jumbo, Relocation","7 days / extended hours","Top-tier regional partner with excellent close speed and high monthly transaction count.",96,"Recommended for Admin Approval","Screening Approved"),
            ("David Brooks","dbrooks@email.com","(602) 555-0188","NMLS-773552","Phoenix","AZ","85004","Phoenix Metro",6,11,35,"English","Conventional, Investor, FHA","Weekdays","Good production readiness and adequate borrower service coverage.",88,"Recommended for Admin Approval","Admin Approved"),
        ]
        for a in demo_agents:
            c.execute('''INSERT INTO agents(full_name,email,phone,nmls_id,city,state,zip_code,market,experience_years,monthly_volume,avg_close_days,languages,specialties,availability,bio,score,ai_recommendation,status,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (*a, now(), now()))
    if c.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0:
        demo_leads = [
            ("Jordan Miller","jordan.miller@email.com","(312) 555-0100","Chicago","IL","60611","Purchase","Website","New",None,"","Looking for local referral partner near Chicago."),
            ("Priya Shah","priya.shah@email.com","(630) 555-0123","Naperville","IL","60540","FHA","Rate Homes Search","Contacted",None,"2026-05-06","Needs Spanish or Mandarin support if available."),
            ("Chris Walker","chris.walker@email.com","(512) 555-0138","Austin","TX","78701","Jumbo","Borrower Portal","New",None,"","High-value relocation lead."),
        ]
        for l in demo_leads:
            c.execute('''INSERT INTO leads(borrower_name,email,phone,city,state,zip_code,loan_type,lead_source,lead_status,assigned_agent_id,last_contact_date,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', l)
    con.commit(); con.close()

init_db()

def role_required(role):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get('role') != role:
                flash("Access restricted. Please sign in with the correct role.", "error")
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapper
    return deco

@app.context_processor
def inject():
    return {"current_user": session.get('name'), "current_role": session.get('role')}

@app.route('/')
def index():
    if session.get('role') == 'screener': return redirect(url_for('screening'))
    if session.get('role') == 'admin': return redirect(url_for('management'))
    if session.get('role') == 'loan_officer': return redirect(url_for('sales'))
    return render_template('landing.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower(); password = request.form.get('password','')
        u = USERS.get(email)
        if u and u['password'] == password:
            session['email']=email; session['role']=u['role']; session['name']=u['name']
            return redirect(url_for('index'))
        flash('Invalid credential. Use the role-specific demo login.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/onboarding', methods=['GET','POST'])
def onboarding():
    if request.method == 'POST':
        f=request.form
        con=conn(); con.execute('''INSERT INTO agents(full_name,email,phone,nmls_id,city,state,zip_code,market,experience_years,monthly_volume,avg_close_days,languages,specialties,availability,bio,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            f.get('full_name'),f.get('email'),f.get('phone'),f.get('nmls_id'),f.get('city'),f.get('state'),f.get('zip_code'),f.get('market'),
            int(f.get('experience_years') or 0),int(f.get('monthly_volume') or 0),int(f.get('avg_close_days') or 0),f.get('languages'),f.get('specialties'),f.get('availability'),f.get('bio'),"Submitted",now(),now()))
        con.commit(); con.close(); flash('Agent profile submitted for screening.', 'success')
        return redirect(url_for('onboarding'))
    return render_template('onboarding.html')

def calculate_score(a):
    score=0
    if a['nmls_id']: score+=15
    if (a['experience_years'] or 0)>=5: score+=20
    elif (a['experience_years'] or 0)>=3: score+=12
    elif (a['experience_years'] or 0)>=1: score+=6
    if (a['monthly_volume'] or 0)>=12: score+=20
    elif (a['monthly_volume'] or 0)>=7: score+=14
    elif (a['monthly_volume'] or 0)>=4: score+=8
    if (a['avg_close_days'] or 99)<=35: score+=18
    elif (a['avg_close_days'] or 99)<=45: score+=12
    elif (a['avg_close_days'] or 99)<=55: score+=6
    if a['city'] and a['state'] and a['zip_code']: score+=10
    if a['languages']: score+=5
    if a['specialties']: score+=5
    if a['bio'] and len(a['bio'])>40: score+=7
    return min(score,100)

def ai_evaluate(a):
    score=calculate_score(a)
    default = {
        "summary": f"{a['full_name']} has been evaluated for local referral readiness across {a['city']}, {a['state']}.",
        "strengths": "Strong borrower coverage and complete contact profile." if score>=70 else "Basic coverage is present, but performance indicators require validation.",
        "risks": "Verify license and production readiness before final activation." if score<85 else "Low operational risk based on submitted production indicators.",
        "recommendation": "Recommended for Admin Approval" if score>=80 else ("Needs Manual Review" if score>=50 else "Recommended for Rejection")
    }
    key=os.getenv('OPENAI_API_KEY')
    if not key or OpenAI is None:
        return score, default
    try:
        client=OpenAI(api_key=key)
        prompt=f"""Evaluate this mortgage/referral agent for client-side referral network onboarding. Return JSON with summary, strengths, risks, recommendation. Agent: {dict(a)}"""
        res=client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":"Return concise professional JSON only."},{"role":"user","content":prompt}], temperature=0.2)
        txt=res.choices[0].message.content.strip().strip('`')
        if txt.startswith('json'): txt=txt[4:].strip()
        data=json.loads(txt)
        default.update({k:data.get(k, default[k]) for k in default})
    except Exception:
        pass
    return score, default

@app.route('/screening')
@role_required('screener')
def screening():
    selected = request.args.get('id')
    con=conn()
    agents=con.execute("SELECT * FROM agents WHERE status IN ('Submitted','Needs Review','Screening Approved','Rejected by Screener') ORDER BY id DESC").fetchall()
    agent=None
    if selected: agent=con.execute("SELECT * FROM agents WHERE id=?",(selected,)).fetchone()
    if not agent and agents: agent=agents[0]
    con.close()
    return render_template('screening.html', agents=agents, agent=agent)

@app.post('/screening/<int:agent_id>/ai')
@role_required('screener')
def run_ai(agent_id):
    con=conn(); a=con.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone()
    score,data=ai_evaluate(a)
    con.execute("UPDATE agents SET score=?, ai_summary=?, ai_strengths=?, ai_risks=?, ai_recommendation=?, updated_at=? WHERE id=?",(score,data['summary'],data['strengths'],data['risks'],data['recommendation'],now(),agent_id))
    con.commit(); con.close(); flash('AI screening updated.', 'success')
    return redirect(url_for('screening', id=agent_id))

@app.post('/screening/<int:agent_id>/action')
@role_required('screener')
def screening_action(agent_id):
    action=request.form.get('action'); notes=request.form.get('notes','')
    status = {'approve':'Screening Approved','review':'Needs Review','reject':'Rejected by Screener'}.get(action,'Needs Review')
    con=conn(); con.execute("UPDATE agents SET status=?, screener_notes=?, updated_at=? WHERE id=?",(status,notes,now(),agent_id)); con.commit(); con.close()
    flash(f'Agent moved to {status}.','success')
    return redirect(url_for('screening', id=agent_id))

@app.route('/management')
@role_required('admin')
def management():
    status=request.args.get('status','all')
    con=conn()
    counts={s: con.execute("SELECT COUNT(*) FROM agents WHERE status=?",(s,)).fetchone()[0] for s in ['Screening Approved','Needs Review','Admin Approved','Admin Rejected','Inactive','Suspended']}
    q="SELECT * FROM agents WHERE status IN ('Screening Approved','Needs Review','Admin Approved','Admin Rejected','Inactive','Suspended','Rejected by Screener') ORDER BY updated_at DESC"
    if status!='all':
        q="SELECT * FROM agents WHERE status=? ORDER BY updated_at DESC"; agents=con.execute(q,(status,)).fetchall()
    else: agents=con.execute(q).fetchall()
    con.close()
    return render_template('management.html', agents=agents, counts=counts, active=status)

@app.post('/management/<int:agent_id>/action')
@role_required('admin')
def management_action(agent_id):
    action=request.form.get('action'); notes=request.form.get('notes','')
    status={'approve':'Admin Approved','reject':'Admin Rejected','inactive':'Inactive','suspend':'Suspended','reactivate':'Admin Approved'}.get(action,'Needs Review')
    con=conn(); con.execute("UPDATE agents SET status=?, admin_notes=?, updated_at=? WHERE id=?",(status,notes,now(),agent_id)); con.commit(); con.close()
    flash(f'Agent status updated to {status}.','success')
    return redirect(url_for('management'))

@app.route('/sales', methods=['GET','POST'])
@role_required('loan_officer')
def sales():
    con=conn()
    if request.method=='POST' and 'file' in request.files:
        file=request.files['file']
        if file.filename and pd:
            df=pd.read_excel(file)
            for _,r in df.iterrows():
                con.execute('''INSERT INTO leads(borrower_name,email,phone,city,state,zip_code,loan_type,lead_source,lead_status,assigned_agent_id,last_contact_date,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(
                    str(r.get('Borrower Name','')),str(r.get('Email','')),str(r.get('Phone','')),str(r.get('City','')),str(r.get('State','')),str(r.get('ZIP Code','')),str(r.get('Loan Type','Purchase')),str(r.get('Lead Source','Excel Upload')),'New',None,'',str(r.get('Notes',''))))
            con.commit(); flash('Excel leads uploaded.','success')
    leads=con.execute("SELECT l.*, a.full_name as agent_name FROM leads l LEFT JOIN agents a ON l.assigned_agent_id=a.id ORDER BY l.id DESC").fetchall()
    agents=con.execute("SELECT * FROM agents WHERE status='Admin Approved' ORDER BY full_name").fetchall()
    con.close()
    return render_template('sales.html', leads=leads, agents=agents)

@app.post('/sales/assign/<int:lead_id>')
@role_required('loan_officer')
def assign(lead_id):
    aid=request.form.get('agent_id')
    con=conn(); con.execute("UPDATE leads SET assigned_agent_id=?, lead_status='Assigned', last_contact_date=? WHERE id=?",(aid,now(),lead_id))
    con.execute("INSERT INTO logs(lead_id,agent_id,channel,summary,created_at) VALUES(?,?,?,?,?)",(lead_id,aid,'Assignment','Loan Officer assigned approved agent to borrower lead.',now()))
    con.commit(); con.close(); flash('Lead assigned to agent.','success')
    return redirect(url_for('sales'))

@app.route('/borrower')
def borrower():
    q=request.args.get('q','').strip().lower()
    con=conn()
    if q:
        agents=con.execute("SELECT * FROM agents WHERE status='Admin Approved' AND (lower(city) LIKE ? OR lower(state) LIKE ? OR zip_code LIKE ? OR lower(languages) LIKE ?) ORDER BY score DESC",(f'%{q}%',f'%{q}%',f'%{q}%',f'%{q}%')).fetchall()
    else:
        agents=con.execute("SELECT * FROM agents WHERE status='Admin Approved' ORDER BY score DESC").fetchall()
    con.close(); return render_template('borrower.html', agents=agents, q=q)

@app.post('/borrower/contact/<int:agent_id>')
def borrower_contact(agent_id):
    channel=request.form.get('channel','SMS')
    con=conn(); con.execute("INSERT INTO logs(lead_id,agent_id,channel,summary,created_at) VALUES(?,?,?,?,?)",(None,agent_id,channel,f'Borrower initiated {channel} contact from public agent search portal.',now()))
    con.commit(); con.close(); flash(f'{channel} contact captured for Sales Dashboard visibility.','success')
    return redirect(url_for('borrower'))

@app.route('/logs')
def logs():
    if not session.get('role'): return redirect(url_for('login'))
    con=conn(); logs=con.execute("SELECT lg.*, a.full_name agent_name, l.borrower_name FROM logs lg LEFT JOIN agents a ON lg.agent_id=a.id LEFT JOIN leads l ON lg.lead_id=l.id ORDER BY lg.id DESC").fetchall(); con.close()
    return render_template('logs.html', logs=logs)

@app.route('/api-flow')
def api_flow():
    if not session.get('role'): return redirect(url_for('login'))
    return render_template('api_flow.html')

if __name__ == '__main__':
    app.run(debug=True)
