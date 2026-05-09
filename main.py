import os
from contextlib import asynccontextmanager

import anthropic
import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI
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


def save_message(sender: str, content: str):
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO messages (patient_id, sender, content) VALUES (%s, %s, %s)",
            (PATIENT_ID, sender, content),
        )


def get_history():
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT sender, content, created_at FROM messages WHERE patient_id = %s ORDER BY id",
            (PATIENT_ID,),
            # row_factory makes rows behave like dicts
        ).fetchall()
    return [{"sender": s, "content": c, "created_at": t.isoformat()} for s, c, t in rows]


@app.post("/chat")
def chat(msg: ChatIn):
    save_message("patient", msg.content)

    history = get_history()
    claude_messages = [
        {"role": "user" if m["sender"] == "patient" else "assistant", "content": m["content"]}
        for m in history
    ]

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=claude_messages,
    )
    reply = response.content[0].text

    save_message("agent", reply)
    return {"reply": reply}


@app.get("/messages")
def messages():
    return get_history()


@app.get("/summary")
def summary():
    history = get_history()
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
        messages=[{"role": "user", "content": f"""Here is the full 
                   transcript of recent patient interactions with the 
                   companion app:\n\n{transcript}\n\nProvide a pre-session 
                   brief for the therapist."""}],
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
