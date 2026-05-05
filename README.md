# PLG — Personalised Lead Generator

AI-powered B2B lead qualification service. Takes a prospect's company info as input and outputs 50 hyper-qualified lead candidates in a Google Sheet.

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd plg-app
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run locally
uvicorn app.main:app --reload --port 8000

# 4. Test
pytest tests/ -v
```

## API

- `GET /health` — Health check
- `POST /generate-leads` — Trigger lead qualification
- `GET /status/{job_id}` — Check job status (async mode)
- `GET /` — HTMX testing UI

## Deployment

Push to `main` branch → auto-deploys to Render via `render.yaml`.

## Tech Stack

- **Backend:** Python 3.11 + FastAPI
- **AI:** Claude + Gemini via OpenRouter
- **Lead Data:** LeadMagic REST API
- **Output:** Google Sheets API
- **Deployment:** Render (free tier)
