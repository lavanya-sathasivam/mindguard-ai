import os
import uuid
import asyncio
import time
import logging
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from services.emotion_service import analyze_message_emotion
from services.crisis_service import check_crisis_and_notify
from services.phq9_service import calculate_phq9_score
from services.coping_service import get_recommendations_for_emotion
from services.chat_service import generate_ai_reply

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mindguard.api")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required. Example: postgresql://user:password@localhost:5432/mindguard")

pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)

app = FastAPI(title="MindGuard AI API")

USER_CONTEXT_CACHE_TTL_SECONDS = 60
user_context_cache: Dict[str, dict] = {}
user_settings_db: Dict[str, Dict[str, Any]] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    user_id: str
    message_text: str


class ChatResponse(BaseModel):
    emotion: str
    sentiment_score: float
    risk_level: str
    reply: str
    is_crisis: bool


class MessageHistoryItem(BaseModel):
    id: str
    text: str
    role: str
    emotion: Optional[str] = None
    sentiment_score: Optional[float] = None
    risk_level: Optional[str] = None
    timestamp: Optional[str] = None


class PHQ9Request(BaseModel):
    user_id: str
    answers: List[int]


class PHQ9Response(BaseModel):
    score: int
    classification: str


class MoodLogRequest(BaseModel):
    user_id: str
    mood_score: int
    journal_text: Optional[str] = None
    stress_level: int


class UserRegister(BaseModel):
    name: str
    email: str
    age: int
    gender: str
    medical_conditions: Optional[str] = None
    stress_trigger: Optional[str] = None
    social_preference: Optional[str] = None
    auth_user_id: Optional[str] = None


class SettingsRequest(BaseModel):
    user_id: str
    reminders_enabled: bool = True
    emergency_contact: Optional[str] = None
    preferred_tone: Optional[str] = "supportive"


class DashboardResponse(BaseModel):
    current_mood_score: float
    stress_level_label: str
    risk_level: str
    weekly_trend_percent: float
    sentiment_trend: List[Dict[str, Any]]
    stress_trend: List[Dict[str, Any]]
    emotion_distribution: List[Dict[str, Any]]
    phq9_trend: List[Dict[str, Any]]


def get_connection():
    return pool.getconn()


def put_connection(connection) -> None:
    pool.putconn(connection)


def db_execute(query: str, params: Optional[tuple] = None) -> None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        put_connection(connection)


def db_fetchone(query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        put_connection(connection)


def db_fetchall(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        put_connection(connection)


def init_db_schema() -> None:
    db_execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            age INTEGER,
            gender TEXT,
            medical_conditions TEXT,
            stress_trigger TEXT,
            social_preference TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            message_text TEXT NOT NULL,
            emotion TEXT,
            sentiment_score DOUBLE PRECISION,
            risk_level TEXT,
            is_user BOOLEAN NOT NULL DEFAULT TRUE,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_messages_user_timestamp ON messages(user_id, timestamp DESC);

        CREATE TABLE IF NOT EXISTS emotion_logs (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            predominant_emotion TEXT,
            avg_sentiment DOUBLE PRECISION,
            recorded_date DATE NOT NULL DEFAULT CURRENT_DATE
        );

        CREATE TABLE IF NOT EXISTS mood_entries (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            mood_score INTEGER CHECK (mood_score >= 1 AND mood_score <= 10),
            journal_text TEXT,
            stress_level INTEGER CHECK (stress_level >= 1 AND stress_level <= 10),
            predicted_stress_increase DOUBLE PRECISION,
            recorded_date DATE NOT NULL DEFAULT CURRENT_DATE
        );

        CREATE TABLE IF NOT EXISTS phq9_results (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            score INTEGER CHECK (score >= 0 AND score <= 27),
            classification TEXT,
            recorded_date DATE NOT NULL DEFAULT CURRENT_DATE
        );

        CREATE TABLE IF NOT EXISTS wellness_plans (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            plan_details JSONB,
            generated_date DATE NOT NULL DEFAULT CURRENT_DATE
        );
        """
    )


@app.on_event("startup")
def on_startup() -> None:
    init_db_schema()
    logger.info("PostgreSQL schema is ready")


@app.on_event("shutdown")
def on_shutdown() -> None:
    pool.closeall()


def ensure_user_access(request: Request, target_user_id: str) -> None:
    require_match = os.getenv("REQUIRE_USER_HEADER_MATCH", "false").lower() == "true"
    if not require_match:
        return
    header_user_id = request.headers.get("x-user-id")
    if not header_user_id:
        raise HTTPException(status_code=401, detail="Missing x-user-id header")
    if str(header_user_id) != str(target_user_id):
        raise HTTPException(status_code=403, detail="Forbidden for this user")


def fetch_recent_messages_for_context(user_id: str, limit: int = 10) -> List[Dict[str, str]]:
    rows = db_fetchall(
        """
        SELECT message_text, is_user
        FROM messages
        WHERE user_id = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (user_id, limit),
    )
    rows.reverse()
    return [
        {
            "role": "user" if row.get("is_user") else "assistant",
            "content": row.get("message_text") or "",
        }
        for row in rows
    ]


def get_cached_user_context(user_id: str) -> dict:
    cache_entry = user_context_cache.get(user_id)
    now = time.time()
    if cache_entry and now - cache_entry.get("ts", 0) < USER_CONTEXT_CACHE_TTL_SECONDS:
        return cache_entry.get("data", {})

    row = db_fetchone("SELECT * FROM users WHERE id = %s", (user_id,))
    data = row or {}
    user_context_cache[user_id] = {"ts": now, "data": data}
    return data


def sentiment_to_mood(sentiment_score: float) -> int:
    scaled = round(((sentiment_score + 1.0) / 2.0) * 9 + 1)
    return max(1, min(10, scaled))


def sentiment_to_stress(sentiment_score: float) -> int:
    scaled = round((1.0 - ((sentiment_score + 1.0) / 2.0)) * 9 + 1)
    return max(1, min(10, scaled))


def stress_label(avg_stress: float) -> str:
    if avg_stress >= 7:
        return "High"
    if avg_stress >= 4:
        return "Moderate"
    return "Low"


@app.get("/")
def root():
    return {"status": "MindGuard backend running", "database": "PostgreSQL"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(msg: ChatMessage):
    user_context = get_cached_user_context(msg.user_id)
    conversation_history = fetch_recent_messages_for_context(msg.user_id, limit=10)

    emotion_task = asyncio.to_thread(analyze_message_emotion, msg.message_text)
    crisis_task = asyncio.to_thread(check_crisis_and_notify, msg.message_text, msg.user_id)

    emotion_payload, crisis_payload = await asyncio.gather(emotion_task, crisis_task)

    emotion = emotion_payload.get("emotion", "neutral")
    sentiment = float(emotion_payload.get("sentiment_score", 0.0) or 0.0)
    is_crisis = bool(crisis_payload)
    risk_level = "High" if is_crisis else "Low"

    reply = await asyncio.to_thread(
        generate_ai_reply,
        text=msg.message_text,
        emotion=emotion,
        sentiment=sentiment,
        risk_level=risk_level,
        is_crisis=is_crisis,
        user_context=user_context,
        conversation_history=conversation_history,
    )

    try:
        db_execute(
            """
            INSERT INTO messages (id, user_id, message_text, emotion, sentiment_score, risk_level, is_user)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE),
                   (%s, %s, %s, %s, %s, %s, FALSE)
            """,
            (
                str(uuid.uuid4()),
                msg.user_id,
                msg.message_text,
                emotion,
                sentiment,
                risk_level,
                str(uuid.uuid4()),
                msg.user_id,
                reply,
                emotion,
                sentiment,
                risk_level,
            ),
        )

        db_execute(
            """
            INSERT INTO emotion_logs (id, user_id, predominant_emotion, avg_sentiment, recorded_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), msg.user_id, emotion, sentiment, str(date.today())),
        )

        db_execute(
            """
            INSERT INTO mood_entries (id, user_id, mood_score, journal_text, stress_level, predicted_stress_increase, recorded_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                msg.user_id,
                sentiment_to_mood(sentiment),
                msg.message_text,
                sentiment_to_stress(sentiment),
                0.0,
                str(date.today()),
            ),
        )
    except Exception as e:
        logger.exception("Chat persistence error: %s", e)

    return ChatResponse(
        emotion=emotion,
        sentiment_score=sentiment,
        risk_level=risk_level,
        reply=reply,
        is_crisis=is_crisis,
    )


@app.post("/api/register")
async def register_user(user: UserRegister):
    try:
        existing_row = db_fetchone("SELECT * FROM users WHERE email = %s", (user.email,))
        if existing_row:
            return {
                "status": "success",
                "user_id": existing_row["id"],
                "name": existing_row.get("name") or user.name or existing_row.get("email"),
            }

        user_id = user.auth_user_id or str(uuid.uuid4())
        db_execute(
            """
            INSERT INTO users (id, name, email, age, gender, medical_conditions, stress_trigger, social_preference)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                user.name,
                user.email,
                user.age,
                user.gender,
                user.medical_conditions,
                user.stress_trigger,
                user.social_preference,
            ),
        )
        return {"status": "success", "user_id": user_id, "name": user.name}
    except Exception as e:
        logger.exception("Registration error: %s", e)
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/api/phq9", response_model=PHQ9Response)
def submit_phq9(data: PHQ9Request):
    result = calculate_phq9_score(data.answers)
    score = int(result.get("score", 0))
    classification = str(result.get("classification", "Minimal depression"))
    try:
        db_execute(
            """
            INSERT INTO phq9_results (id, user_id, score, classification, recorded_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), data.user_id, score, classification, str(date.today())),
        )
    except Exception as e:
        logger.exception("PHQ9 save error: %s", e)
    return PHQ9Response(score=score, classification=classification)


@app.post("/api/mood")
def log_mood(data: MoodLogRequest):
    try:
        db_execute(
            """
            INSERT INTO mood_entries (id, user_id, mood_score, journal_text, stress_level, predicted_stress_increase, recorded_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                data.user_id,
                data.mood_score,
                data.journal_text,
                data.stress_level,
                0.0,
                str(date.today()),
            ),
        )
        return {"status": "saved"}
    except Exception as e:
        logger.exception("Mood log save error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save mood log")


@app.get("/api/dashboard/{user_id}", response_model=DashboardResponse)
async def get_dashboard(user_id: str, request: Request):
    ensure_user_access(request, user_id)

    today = date.today()
    last_30_days = today - timedelta(days=30)

    try:
        mood_rows = db_fetchall(
            """
            SELECT mood_score, stress_level, recorded_date
            FROM mood_entries
            WHERE user_id = %s AND recorded_date >= %s
            ORDER BY recorded_date ASC
            """,
            (user_id, str(last_30_days)),
        )
        message_rows = db_fetchall(
            """
            SELECT emotion, sentiment_score, timestamp
            FROM messages
            WHERE user_id = %s AND timestamp >= %s
            ORDER BY timestamp ASC
            """,
            (user_id, str(last_30_days)),
        )
        phq_rows = db_fetchall(
            """
            SELECT score, classification, recorded_date
            FROM phq9_results
            WHERE user_id = %s
            ORDER BY recorded_date ASC
            """,
            (user_id,),
        )

        current_mood_score = round(
            sum(float(row.get("mood_score", 0)) for row in mood_rows) / max(1, len(mood_rows)),
            2,
        )
        avg_stress = round(
            sum(float(row.get("stress_level", 0)) for row in mood_rows) / max(1, len(mood_rows)),
            2,
        )
        stress_level_label = stress_label(avg_stress)

        recent_scores = [float(row.get("mood_score", 0)) for row in mood_rows[-3:]]
        previous_scores = [float(row.get("mood_score", 0)) for row in mood_rows[-6:-3]]
        recent_avg = sum(recent_scores) / max(1, len(recent_scores))
        prev_avg = sum(previous_scores) / max(1, len(previous_scores))
        weekly_trend_percent = 0.0 if prev_avg == 0 else round(((recent_avg - prev_avg) / prev_avg) * 100, 2)

        latest_phq = phq_rows[-1] if phq_rows else None
        if latest_phq and "severe" in str(latest_phq.get("classification", "")).lower():
            risk_level = "High"
        elif latest_phq and "moderate" in str(latest_phq.get("classification", "")).lower():
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        by_day: Dict[str, List[float]] = {}
        for row in message_rows:
            timestamp_value = row.get("timestamp")
            day_key = str(timestamp_value)[:10] if timestamp_value else str(today)
            by_day.setdefault(day_key, []).append(float(row.get("sentiment_score", 0) or 0))

        sentiment_trend = [
            {"day": day_key, "sentiment": round(sum(values) / len(values), 2)}
            for day_key, values in sorted(by_day.items())[-7:]
        ]

        stress_by_day: Dict[str, List[float]] = {}
        for row in mood_rows:
            day_key = str(row.get("recorded_date"))
            stress_by_day.setdefault(day_key, []).append(float(row.get("stress_level", 0) or 0))
        stress_trend = [
            {"day": day_key, "stress": round(sum(values) / len(values), 2)}
            for day_key, values in sorted(stress_by_day.items())[-7:]
        ]

        emotion_counts: Dict[str, int] = {}
        for row in message_rows:
            emotion = (row.get("emotion") or "neutral").capitalize()
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        emotion_distribution = [{"name": name, "value": value} for name, value in emotion_counts.items()]

        phq9_trend = [
            {"month": str(row.get("recorded_date"))[:7], "score": int(row.get("score", 0) or 0)}
            for row in phq_rows
        ]

        return DashboardResponse(
            current_mood_score=current_mood_score,
            stress_level_label=stress_level_label,
            risk_level=risk_level,
            weekly_trend_percent=weekly_trend_percent,
            sentiment_trend=sentiment_trend,
            stress_trend=stress_trend,
            emotion_distribution=emotion_distribution,
            phq9_trend=phq9_trend,
        )
    except Exception as e:
        logger.exception("Dashboard fetch error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")


@app.get("/api/messages/{user_id}", response_model=List[MessageHistoryItem])
async def get_messages(user_id: str, request: Request, limit: int = 50):
    ensure_user_access(request, user_id)
    safe_limit = max(1, min(limit, 200))
    try:
        rows = db_fetchall(
            """
            SELECT id, message_text, is_user, emotion, sentiment_score, risk_level, timestamp
            FROM messages
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (user_id, safe_limit),
        )
        rows.reverse()
        return [
            MessageHistoryItem(
                id=str(row.get("id")),
                text=row.get("message_text") or "",
                role="user" if row.get("is_user") else "assistant",
                emotion=row.get("emotion"),
                sentiment_score=float(row.get("sentiment_score")) if row.get("sentiment_score") is not None else None,
                risk_level=row.get("risk_level"),
                timestamp=str(row.get("timestamp")) if row.get("timestamp") else None,
            )
            for row in rows
        ]
    except Exception as e:
        logger.exception("Messages fetch error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@app.post("/api/settings")
def save_settings(data: SettingsRequest):
    user_settings_db[data.user_id] = data.dict()
    return {"status": "success", "settings": data}
