# OpportunityHub — Backend

Flask + PostgreSQL API for the OpportunityHub platform (opportunities hub + teacher promotion
exam prep hub). See the [main project README](https://github.com/Ayamba12/opportunity-hub) for
full context, architecture, and local setup across the whole stack (frontend, agents, etc.).

## Deploying on Render

1. **New Web Service** → connect this repository.
2. **Build command**: `pip install -r requirements.txt && flask db upgrade`
3. **Start command**: `gunicorn run:app`
4. **Environment variables** (Render → Environment tab):

   | Variable | Value |
   |---|---|
   | `FLASK_ENV` | `production` |
   | `SECRET_KEY` | generate a random secret |
   | `JWT_SECRET_KEY` | generate a random secret |
   | `DATABASE_URL` | your Postgres connection string (plain `postgresql://...` — auto-normalized to the `psycopg` dialect in code) |
   | `CORS_ORIGINS` | your deployed frontend's origin, e.g. `https://yourapp.vercel.app` |
   | `AI_AGENT_API_KEY` | optional — only needed if using the scholarship-finding agent's ingest endpoint |
   | `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `STORAGE_BUCKET` | S3-compatible object storage for opportunity images (bucket must be public-read) |

   `RENDER_EXTERNAL_URL` is set automatically by Render — no action needed. It activates a
   background keep-alive ping (`app/keepalive.py`) that pings the app's own `/api/health` every
   12 minutes to reduce free-tier spin-downs. Harmless and inert on paid plans.

5. After the first deploy, create an admin account by running `python seed.py` against the
   production database once (via Render's shell, or locally with `DATABASE_URL` pointed at
   production) — **then change that seeded password immediately.**

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY at minimum
export FLASK_APP=run.py
flask db upgrade
python seed.py          # optional: sample data + admin login
flask run --port 5000
```

## Tests

```bash
python -m pytest tests/ -v
```
