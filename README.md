# Rate Homes Agent Network MVP

Client-facing local MVP with separate Screener, Admin, Loan Officer and public Borrower/Agent flows.

## Mac run steps

```bash
cd gr_agent_network_client_mvp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 app.py
```

Open: http://127.0.0.1:5000

## Demo logins

- Screener: screener@ratehomes.com / screen123
- Admin: admin@ratehomes.com / admin123
- Loan Officer: lo@ratehomes.com / loan123

## OpenAI key

Paste your key in `.env`:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxx
FLASK_SECRET_KEY=any-random-secret
```

OpenAI is used only from the Screener Dashboard when clicking Run AI Screening.
