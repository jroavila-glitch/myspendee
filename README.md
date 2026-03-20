# MySpendee

Expense tracking dashboard — PDF upload → Claude AI extraction → MXN dashboard.

## Project Structure

```
myspendee/
├── backend/          FastAPI + PostgreSQL
└── frontend/         React + Vite
```

## Local Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # set VITE_API_URL=http://localhost:8000
npm run dev
```

## Deployment

### Backend → Railway

1. Create a new Railway project
2. Add a PostgreSQL database service
3. Create a new service from this GitHub repo, pointing to the `backend/` folder
4. Set environment variables:
   - `ANTHROPIC_API_KEY`
   - `DATABASE_URL` (auto-filled by Railway from the PostgreSQL plugin)
   - `FRONTEND_URL` (your Vercel URL)
5. Railway auto-detects the Dockerfile

### Frontend → Vercel

1. Import this repo on Vercel
2. Set Root Directory to `frontend`
3. Set environment variable:
   - `VITE_API_URL` = your Railway backend URL (e.g. `https://myspendee-backend.up.railway.app`)
4. Update `vercel.json` with your actual Railway URL
5. Deploy

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Backend (Railway) | Claude API key |
| `DATABASE_URL` | Backend (Railway) | PostgreSQL connection string |
| `FRONTEND_URL` | Backend (Railway) | Vercel frontend URL (for CORS) |
| `VITE_API_URL` | Frontend (Vercel) | Railway backend URL |
