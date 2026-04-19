# MindGuard AI - Predictive Mental Health Intelligence Platform

MindGuard AI is a modern healthcare AI SaaS platform. It features real-time analytics, an AI chat interface, PHQ-9 assessments, and mood logging.

## AI Conversation Engine

MindGuard AI uses a **true conversational AI system** powered by large language models (LLMs). Every response is:
- **Dynamically generated** by an LLM (not templated)
- **Context-aware** using up to 10 previous messages for continuity
- **Emotion-informed** with real-time sentiment analysis (VADER + RoBERTa)
- **Crisis-aware** with immediate safety interventions
- **Naturally varied** - the same input generates different responses each time

### Response Generation Pipeline
1. **User Message** → Emotion detection (VADER + HuggingFace RoBERTa)
2. **Conversation History** → Fetch up to 10 prior messages
3. **LLM Processing** → Priority: Gemini → OpenAI → Smart Fallback
4. **Storage** → All exchanges persisted with emotion/sentiment metadata
5. **UI Display** → Real-time updates with conversation flow (no templates, no static advice blocks)

### Enabling True LLM Responses
To move beyond the smart fallback, add LLM credentials to `.env`:
```bash
# Option 1: Google Gemini (Preferred)
GEMINI_API_KEY=your-key-here
GEMINI_CHAT_MODEL=gemini-1.5-flash

# Option 2: OpenAI (Optional)
OPENAI_API_KEY=sk-your-key-here
OPENAI_CHAT_MODEL=gpt-4o-mini  # or gpt-4-turbo, gpt-3.5-turbo
```

Without LLM keys, the system falls back to **smart reflection-based responses** that invite deeper conversation—still human-like, but not as personalized as full LLM generation.

## Tech Stack
- **Frontend**: Next.js 14, TailwindCSS, ShadCN UI, Recharts, Framer Motion
- **Backend**: FastAPI, Python, Pydantic, HuggingFace Transformers, VADER
- **Database**: PostgreSQL
- **LLM Integrations**: OpenAI API, Google Gemini API
- **Automation**: n8n workflows

## Local Development Setup

### 1. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 2. Backend
```bash
cd .
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. PostgreSQL setup
Create a PostgreSQL database and set `DATABASE_URL` in `.env` (see `.env.example`).
The backend auto-creates required tables on startup.

## Database (Supabase)

- **Platform used:** Supabase (PostgreSQL + Realtime + Auth)
- **Schema summary:** the project includes SQL in `supabase/schema.sql` and creates these primary tables:
	- `users` — UUID primary key, email, profile fields, created_at
	- `messages` — user_id FK, message_text, emotion, sentiment_score, risk_level, timestamp
	- `emotion_logs` — user_id FK, predominant_emotion, avg_sentiment, recorded_date
	- `mood_entries` — user_id FK, mood_score (1-10), journal_text, stress_level, predicted_stress_increase, recorded_date
	- `phq9_results` — user_id FK, score (0-27), classification, recorded_date
	- `wellness_plans` — user_id FK, `plan_details` (JSONB), generated_date

- **Row Level Security (RLS):** the SQL enables RLS and creates policies so users can only manage their own rows (see `supabase/schema.sql`).

- **Realtime:** publications for `messages`, `mood_entries`, and `phq9_results` are added to Supabase realtime in the SQL so the frontend can subscribe to live updates.

- **How to apply:**
	1. Create a Supabase project at https://supabase.com
	2. In the SQL editor, run the contents of `supabase/schema.sql` to create tables, policies and realtime config.
	3. Create a service role key (or use the project URL + anon key for client use where appropriate). Store keys in your environment (see below).

- **Env vars (examples):** make sure to populate `.env` or your deployment secrets with:
	- `DATABASE_URL` — Postgres connection string (used by backend)
	- `SUPABASE_URL` — Supabase project URL (optional, for client usage)
	- `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` — keys for client/server as appropriate

Notes: prefer using the `SERVICE_ROLE_KEY` only on server-side processes; use RLS for client safety.

## Automation (n8n)

- **Platform used:** n8n for automation/workflows. Example workflows are in the `automation/` folder:
	- `daily_reminder_workflow.json` — Cron-triggered node that sends a daily reminder email (uses SendGrid HTTP request node). Edit the API key in the node or supply via n8n credentials.
	- `crisis_alert_workflow.json` — Webhook that publishes a Slack emergency notice when the backend posts a crisis alert payload.

- **How to use:**
	1. Install and run n8n locally or in your infra (https://n8n.io).
	2. Import the JSON workflows from `automation/` into your n8n instance.
	3. Update node credentials (SendGrid API key, Slack credentials) in n8n credentials manager.
	4. Set `N8N_WEBHOOK_URL` in your backend environment to the webhook endpoint URL for the `crisis_alert` webhook (e.g. `https://YOUR_N8N_HOST/webhook/crisis-alert`).

- **Render / deployment note:** `render.yaml` expects `DATABASE_URL` and `N8N_WEBHOOK_URL` as env vars for hosted deployments. See `implementation_plan.md` for Render/Vercel integration notes.

If you'd like, I can also:
- Add a short `supabase/README.md` with step-by-step instructions to create the project and run the SQL.
- Add an `automation/README.md` with import steps for the n8n workflows and recommended credential setup.
