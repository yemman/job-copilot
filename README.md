# Job Copilot

A local-first (GCP Cloud Run–ready) personal job-search assistant built with **React (Vite + TypeScript) + Python FastAPI + SQLite**.

## Key Features
- **Profile & Resume Matching**: Upload `.pdf`, `.txt`, or `.md` resumes (auto-extracts skills), configure target roles, locations, work mode, and dealbreakers.
- **3–5 Daily Job Suggestions (Sunday–Wednesday)**: Built-in APScheduler runs Sun–Wed (plus a manual **"Generate Today's Picks"** button anytime and a Cloud-Scheduler-ready `POST /api/cron/daily-digest` endpoint).
- **Public ATS & Job APIs + Paste URL/Text**: Native fetchers for **Greenhouse**, **Lever**, **Ashby**, **Remotive**, and **Arbeitnow**, plus manual URL/text import.
- **Gemini AI + Offline Heuristic Fallback**: Uses Gemini (`GEMINI_API_KEY`) for fit rationales, reranking, and outreach drafting, and automatically falls back to deterministic heuristic scoring + editable templates offline.
- **Transparent Learning Loop (HITL)**: Approving, skipping (with reason), outreach replies, interviews, and rejections update inspectable `LearnedRule` weights. You can edit, lock/unlock, disable, or add manual rules in **What It Learned**.
- **Strict Human-in-the-Loop & Connection-First Gate**:
  - Approving a job lands it in **Connection Search** first — matching contacts at the target company (from manual contacts or LinkedIn `Connections.csv`) and providing a 1-click LinkedIn People search link.
  - Outreach drafts (`linkedin_connect_note` ≤ 300 chars, `linkedin_dm`, `email`) start as `draft`, require explicit **Approve**, and are copied/sent manually by you before clicking **Mark as Sent**.
  - Skipping outreach to apply directly requires an explicit override reason.

---

## Quickstart (Local)

1. Copy `.env.example` to `.env` (optional — works offline out of the box):
   ```bash
   cp .env.example .env
   # Optionally set GEMINI_API_KEY=your-key
   ```
2. Start both backend and frontend:
   ```bash
   ./start-dev.sh
   ```
3. Open **http://localhost:5173**.
   - Click **Load Demo Data** in the top bar if you want sample jobs, contacts, and learned rules immediately, then click **Generate Today's Picks**.

### Running Backend & Frontend Separately
- **Backend:**
  ```bash
  cd backend
  ./.venv/bin/uvicorn app.main:app --reload --port 8000
  ```
- **Frontend:**
  ```bash
  cd frontend
  npm run dev
  ```

---

## Importing Your LinkedIn Connections (`Connections.csv`)
1. On LinkedIn, go to **Settings & Privacy → Data Privacy → Get a copy of your data**.
2. Select **Connections** and download `Connections.csv`.
3. In Job Copilot, open **Network & CSV → Import LinkedIn Connections CSV**.

---

## Deploying to GCP Cloud Run + Cloud Scheduler (Later)
1. Provision a managed PostgreSQL database (e.g., Neon / Supabase / Cloud SQL) and set `DATABASE_URL` so data persists across stateless container restarts.
2. Build & deploy the included `Dockerfile` to **Cloud Run** with environment variables:
   - `DATABASE_URL`
   - `GEMINI_API_KEY`
   - `CRON_SECRET`
   - `ENABLE_SCHEDULER=false` (let Cloud Scheduler trigger the cron endpoint instead)
3. Create a **Cloud Scheduler** job with schedule `0 9 * * 0-3` (`Asia/Jerusalem` or your timezone) calling `POST https://<your-service>/api/cron/daily-digest` with header `X-Cron-Secret: <CRON_SECRET>`.
4. Put Cloud Run behind **Identity-Aware Proxy (IAP)** or authentication before exposing personal resume/contacts publicly.
