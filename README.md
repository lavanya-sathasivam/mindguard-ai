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
