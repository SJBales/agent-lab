import os
from contextlib import asynccontextmanager

import anthropic
import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

# A connection pool, not a single connection. The pool keeps a few
# connections open and hands them out to requests. Opening a new
# connection per request would be very slow.
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(lifespan=lifespan)

PATIENT_ID = 1

SYSTEM_PROMPT = """You are a supportive companion app that works
alongside the patient's licensed therapist. You are NOT a therapist
and do not give clinical advice or diagnoses. Your role is to help
the patient notice and articulate what they're feeling between sessions,
so their therapist has richer context for live work.

Be warm, curious, and brief. Ask one gentle follow-up question when
it would help the patient go deeper. If the patient mentions self-harm,
suicide, or a crisis, tell them to contact their therapist or call 988
(US) immediately."""


class ChatIn(BaseModel):
    content: str


class SessionIn(BaseModel):
    title: str | None = None


class SteeringIn(BaseModel):
    guidance: str


def create_session(patient_id: int, title: str | None):
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO sessions (patient_id, title) VALUES (%s, %s) RETURNING id, title, started_at",
            (patient_id, title),
        ).fetchone()
    return {"id": row[0], "title": row[1], "started_at": row[2].isoformat(), "message_count": 0}


def list_sessions(patient_id: int):
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.started_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count
            FROM sessions s
            WHERE s.patient_id = %s
            ORDER BY s.started_at DESC
            """,
            (patient_id,),
        ).fetchall()
    return [
        {"id": r[0], "title": r[1], "started_at": r[2].isoformat(), "message_count": r[3]}
        for r in rows
    ]


def session_belongs_to_patient(session_id: int, patient_id: int) -> bool:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE id = %s AND patient_id = %s",
            (session_id, patient_id),
        ).fetchone()
    return row is not None


def save_message(session_id: int, sender: str, content: str):
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO messages (patient_id, session_id, sender, content) VALUES (%s, %s, %s, %s)",
            (PATIENT_ID, session_id, sender, content),
        )


def get_session_messages(session_id: int):
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT sender, content, created_at FROM messages WHERE session_id = %s ORDER BY id",
            (session_id,),
        ).fetchall()
    return [{"sender": s, "content": c, "created_at": t.isoformat()} for s, c, t in rows]


def get_patient_messages(patient_id: int):
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT sender, content, created_at FROM messages WHERE patient_id = %s ORDER BY id",
            (patient_id,),
        ).fetchall()
    return [{"sender": s, "content": c, "created_at": t.isoformat()} for s, c, t in rows]


def require_session(session_id: int):
    if not session_belongs_to_patient(session_id, PATIENT_ID):
        raise HTTPException(status_code=404, detail="Session not found")


def get_steering(patient_id: int) -> dict:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT guidance, updated_at FROM patient_steering WHERE patient_id = %s",
            (patient_id,),
        ).fetchone()
    if row is None:
        return {"guidance": "", "updated_at": None}
    return {"guidance": row[0], "updated_at": row[1].isoformat()}


def upsert_steering(patient_id: int, guidance: str) -> dict:
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO patient_steering (patient_id, guidance, updated_at)
            VALUES (%s, %s, now())
            ON CONFLICT (patient_id) DO UPDATE
              SET guidance = EXCLUDED.guidance,
                  updated_at = now()
            RETURNING guidance, updated_at
            """,
            (patient_id, guidance),
        ).fetchone()
    return {"guidance": row[0], "updated_at": row[1].isoformat()}


def build_chat_system_prompt(patient_id: int) -> str:
    guidance = get_steering(patient_id)["guidance"].strip()
    if not guidance:
        return SYSTEM_PROMPT
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Guidance from the patient's licensed therapist (follow this when "
        f"shaping your responses, but do not quote it back to the patient):\n"
        f"{guidance}"
    )


@app.post("/sessions")
def new_session(body: SessionIn | None = None):
    title = body.title if body else None
    return create_session(PATIENT_ID, title)


@app.get("/sessions")
def all_sessions():
    return list_sessions(PATIENT_ID)


@app.post("/sessions/{session_id}/chat")
def chat(session_id: int, msg: ChatIn):
    require_session(session_id)
    save_message(session_id, "patient", msg.content)

    history = get_session_messages(session_id)
    claude_messages = [
        {"role": "user" if m["sender"] == "patient" else "assistant", "content": m["content"]}
        for m in history
    ]

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=400,
        system=build_chat_system_prompt(PATIENT_ID),
        messages=claude_messages,
    )
    reply = response.content[0].text

    save_message(session_id, "agent", reply)
    return {"reply": reply}


@app.get("/steering")
def read_steering():
    return get_steering(PATIENT_ID)


@app.put("/steering")
def write_steering(body: SteeringIn):
    return upsert_steering(PATIENT_ID, body.guidance)


@app.get("/sessions/{session_id}/messages")
def session_messages_route(session_id: int):
    require_session(session_id)
    return get_session_messages(session_id)


@app.get("/sessions/{session_id}/summary")
def session_summary(session_id: int):
    require_session(session_id)
    history = get_session_messages(session_id)
    if not history:
        return {"summary": "No messages in this session yet."}

    transcript = "\n".join(f"{m['sender'].upper()}: {m['content']}" for m in history)

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=600,
        system="""You are a clinical assistant summarizing a single
        between-session check-in for the patient's therapist. Identify
        the main themes, emotional tone, anything the patient seems
        stuck on, and one or two suggested topics for the next live
        session. Be concise and clinically useful.""",
        messages=[
            {
                "role": "user",
                "content": f"Transcript of this check-in session:\n\n{transcript}\n\nProvide a brief for the therapist.",
            }
        ],
    )
    return {"summary": response.content[0].text}


@app.get("/summary")
def summary():
    """Cross-session brief over all of the patient's interactions."""
    history = get_patient_messages(PATIENT_ID)
    if not history:
        return {"summary": "No conversations yet."}

    transcript = "\n".join(f"{m['sender'].upper()}: {m['content']}" for m in history)

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=800,
        system="""You are a clinical assistant summarizing a patient's
        between-session interactions for their therapist. Identify
        recurring themes, emotional patterns, things the patient seems
        stuck on, and suggested topics for the next live session. Be
        concise and clinically useful.""",
        messages=[
            {
                "role": "user",
                "content": f"Here is the full transcript of recent patient interactions with the companion app:\n\n{transcript}\n\nProvide a pre-session brief for the therapist.",
            }
        ],
    )
    return {"summary": response.content[0].text}


@app.get("/")
def chat_page():
    return FileResponse("chat.html")


@app.get("/therapist")
def therapist_page():
    return FileResponse("dashboard.html")


@app.get("/healthz")
def health():
    """Render hits this to check the service is alive."""
    return {"ok": True}
