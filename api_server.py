import logging
import asyncio
import contextlib

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from openai import RateLimitError

import config
import db_history
from brain import build_agent, ask


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_server")


# ============================================================
# SHARED AGENT
# ============================================================
#
# One agent is built at startup and reused for every request, since
# rebuilding it (reconnecting to both MCP servers) on every message
# would be far too slow. Conversation history is what's kept separate
# per user -- see db_history.py -- not the agent itself.

_agent = None


# ============================================================
# ONE SIMPLE LOCK
# ============================================================
#
# Only needed to stop two rapid requests from reading -> generating ->
# saving at the same time and stepping on each other's history. A
# single global lock is simpler than a lock per session and is more
# than fast enough at this application's scale -- it just means two
# people's messages are answered one after another rather than at the
# exact same instant, which is not noticeable in practice.

_lock = asyncio.Lock()


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):

    message: str

    session_id: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message_length(cls, value: str) -> str:
        if len(value) > config.MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message exceeds the maximum allowed length of "
                f"{config.MAX_MESSAGE_LENGTH} characters."
            )
        return value


# ============================================================
# AUTH DEPENDENCY
# ============================================================

async def verify_api_key(x_api_key: str | None = Header(default=None)):
    if not config.APP_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: APP_API_KEY is not set.",
        )
    if x_api_key != config.APP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):

    global _agent

    config.require_app_api_key()

    # Make sure the chat_history table exists before anything else runs.
    db_history.init_db()

    # Build the shared agent once.
    _agent = await build_agent()

    yield


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Agentic AI API",
    lifespan=lifespan,
)


# ============================================================
# SAFETY NET: never let ANY unhandled error return a non-JSON body
# ============================================================
#
# Every route above already catches its own expected failures. This
# catch-all exists purely so that a genuinely unexpected bug (e.g. a
# typo in a future change) still returns clean JSON instead of
# Starlette's default plain-text error page -- which is what caused a
# confusing "JSONDecodeError" on the CLIENT side rather than a clear
# message, the first time this happened.

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on the server. Please try again."},
    )


# ============================================================
# CHAT ENDPOINT
# ============================================================

@app.post("/chat")
async def chat(request: ChatRequest, x_api_key: str | None = Header(default=None)):

    await verify_api_key(x_api_key)

    global _agent

    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent is not ready.")

    # --------------------------------------------------------
    # VALIDATE MESSAGE
    # --------------------------------------------------------

    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # --------------------------------------------------------
    # SESSION ID
    # --------------------------------------------------------
    #
    # No session_id supplied -> this is a new conversation, generate one.
    # A session_id IS supplied -> just use it. If it happens to have no
    # history yet (new, mistyped, or from a previous server run before
    # this feature existed), it simply starts empty -- there is nothing
    # to "not find" the way there was with the old in-memory store.

    session_id = request.session_id or db_history.new_session_id()

    # --------------------------------------------------------
    # PROCESS THIS CONVERSATION
    # --------------------------------------------------------

    async with _lock:

        try:
            history = db_history.get_history(session_id)
            response = await ask(_agent, message, history)
            db_history.append_turn(session_id, message, response)
        except RateLimitError as e:
            logger.error(f"[session={session_id}] OpenAI rate limit hit: {e}")
            raise HTTPException(
                status_code=503,
                detail="The assistant is currently busy. Please try again in a moment.",
            )
        except Exception:
            logger.exception(f"[session={session_id}] Unexpected error handling chat request")
            raise HTTPException(
                status_code=500,
                detail="Something went wrong while processing your message. Please try again.",
            )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "session_id": session_id,
        "response": response,
    }


# ============================================================
# SESSION COUNT (admin/debug)
# ============================================================

@app.get("/sessions/count")
async def session_count(x_api_key: str | None = Header(default=None)):
    await verify_api_key(x_api_key)
    return {
        "total_conversations_ever_stored": db_history.session_count()
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():
    # Deliberately NOT behind auth -- load balancers / uptime monitors
    # need to reach this without a key.
    return {
        "status": "ok",
        "agent_ready": _agent is not None,
    }