import asyncio
import contextlib
import logging

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, field_validator
from openai import RateLimitError

import config
from brain import build_agent, ask
from session_manager import SessionManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_server")


# ============================================================
# SESSION MANAGER
# ============================================================

session_manager = SessionManager(
    session_ttl_seconds=3600,
    max_requests_per_minute=config.MAX_REQUESTS_PER_SESSION_PER_MINUTE,
)


# ============================================================
# SHARED AGENT
# ============================================================

_agent = None


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
#
# Checks a single SHARED secret sent in the X-API-Key header on every
# request. This stops unauthenticated/unknown callers from reaching the
# API at all. It does NOT give individual users their own identity --
# see the note in config.py for exactly what this does and doesn't
# protect against.

async def verify_api_key(x_api_key: str | None = Header(default=None)):
    if not config.APP_API_KEY:
        # Fail loudly at request time if the server was misconfigured,
        # rather than silently accepting every request with no key set.
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: APP_API_KEY is not set.",
        )
    if x_api_key != config.APP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ============================================================
# SESSION CLEANUP
# ============================================================

async def cleanup_loop():

    while True:

        try:

            await asyncio.sleep(600)

            removed = await session_manager.cleanup_expired()

            if removed > 0:

                logger.info(f"Removed {removed} expired session(s).")

        except asyncio.CancelledError:

            raise

        except Exception as error:

            logger.error(f"Session cleanup error: {error}")


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):

    global _agent

    config.require_app_api_key()

    # Build the shared agent once.
    _agent = await build_agent()

    cleanup_task = asyncio.create_task(
        cleanup_loop()
    )

    try:

        yield

    finally:

        cleanup_task.cancel()

        with contextlib.suppress(
            asyncio.CancelledError
        ):

            await cleanup_task


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Agentic AI API",
    lifespan=lifespan,
)


# ============================================================
# CHAT ENDPOINT
# ============================================================

@app.post("/chat", dependencies=[])
async def chat(request: ChatRequest, x_api_key: str | None = Header(default=None)):

    await verify_api_key(x_api_key)

    global _agent

    if _agent is None:

        raise HTTPException(
            status_code=503,
            detail="Agent is not ready."
        )

    # --------------------------------------------------------
    # VALIDATE MESSAGE
    # --------------------------------------------------------

    message = request.message.strip()

    if not message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    # --------------------------------------------------------
    # GET OR CREATE SESSION
    # --------------------------------------------------------

    session_id = request.session_id

    # No session ID means this is a new conversation.
    if session_id is None:

        session_id = await session_manager.create_session()

    # Existing session ID must belong to an active session.
    else:

        exists = await session_manager.session_exists(
            session_id
        )

        if not exists:

            raise HTTPException(
                status_code=404,
                detail="Session not found."
            )

    # --------------------------------------------------------
    # RATE LIMIT THIS SESSION
    # --------------------------------------------------------

    allowed = await session_manager.check_rate_limit(session_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many requests for this session. Limit is "
                f"{config.MAX_REQUESTS_PER_SESSION_PER_MINUTE} per minute."
            ),
        )

    # --------------------------------------------------------
    # GET THE LOCK FOR THIS SESSION
    # --------------------------------------------------------

    try:
        session_lock = await session_manager.get_session_lock(
            session_id
        )
    except ValueError:
        # Narrow race: session expired/was deleted between the
        # exists-check above and this call.
        raise HTTPException(status_code=404, detail="Session not found.")

    # --------------------------------------------------------
    # PROCESS THIS CONVERSATION
    # --------------------------------------------------------
    #
    # Different sessions have different locks and therefore
    # can execute concurrently.
    #
    # Requests belonging to the SAME session are processed
    # sequentially so conversation ordering is preserved.
    #

    async with session_lock:

        # Get history belonging ONLY to this session.
        history = await session_manager.get_history(
            session_id
        )

        # Send this session's history to the shared agent.
        try:
            response = await ask(
                _agent,
                message,
                history
            )
        except RateLimitError as e:
            logger.error(f"[session={session_id}] OpenAI rate limit hit: {e}")
            raise HTTPException(
                status_code=503,
                detail="The assistant is currently busy. Please try again in a moment.",
            )
        except Exception as e:
            logger.exception(f"[session={session_id}] Unexpected error handling chat request")
            raise HTTPException(
                status_code=500,
                detail="Something went wrong while processing your message. Please try again.",
            )

        # Save the new turn to THIS session.
        try:
            await session_manager.append_turn(
                session_id,
                message,
                response
            )
        except ValueError:
            # Session was deleted mid-request (very narrow race). The
            # user still gets their real answer below; it just won't
            # be remembered for a follow-up message.
            logger.warning(f"[session={session_id}] Session vanished before turn could be saved.")

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "session_id": session_id,
        "response": response,
    }


# ============================================================
# SESSION COUNT
# ============================================================

@app.get("/sessions/count")
async def session_count(x_api_key: str | None = Header(default=None)):
    await verify_api_key(x_api_key)
    count = await session_manager.session_count()
    return {
        "active_sessions": count
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