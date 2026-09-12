import asyncio
import time
import uuid


class SessionManager:

    def __init__(
        self,
        session_ttl_seconds: int = 3600,
        max_requests_per_minute: int = 10,
    ):

        self.session_ttl_seconds = session_ttl_seconds
        self.max_requests_per_minute = max_requests_per_minute

        # Stores conversation data.
        #
        # {
        #     session_id: {
        #         "history": [...],
        #         "last_active": timestamp
        #     }
        # }
        self._sessions = {}

        # Protects creation/deletion/access to the session
        # collections themselves.
        self._lock = asyncio.Lock()

        # One lock per session.
        #
        # Different users can run concurrently because they
        # have different locks.
        #
        # Requests belonging to the same session are serialized.
        self._session_locks = {}

        # Per-session request timestamps, for rate limiting.
        # { session_id: [timestamp, timestamp, ...] }
        self._request_timestamps = {}

    async def create_session(self) -> str:

        session_id = str(
            uuid.uuid4()
        )

        async with self._lock:

            self._sessions[session_id] = {
                "history": [],
                "last_active": time.time(),
            }

            self._session_locks[session_id] = (
                asyncio.Lock()
            )

            self._request_timestamps[session_id] = []

        return session_id

    async def session_exists(
        self,
        session_id: str
    ) -> bool:

        async with self._lock:

            return session_id in self._sessions

    async def check_rate_limit(self, session_id: str) -> bool:
        """
        Returns True if this session is within its rate limit and the
        request should proceed. Returns False if the session has made
        too many requests in the last 60 seconds and should be rejected.

        This protects the SHARED OpenAI rate limit from being exhausted
        by one session, at the cost of all other sessions' requests
        failing too.
        """
        now = time.time()
        async with self._lock:
            timestamps = self._request_timestamps.setdefault(session_id, [])
            # Drop timestamps older than the rolling 60-second window.
            recent = [t for t in timestamps if now - t < 60]
            if len(recent) >= self.max_requests_per_minute:
                self._request_timestamps[session_id] = recent
                return False
            recent.append(now)
            self._request_timestamps[session_id] = recent
            return True

    async def get_history(
        self,
        session_id: str
    ) -> list:

        async with self._lock:

            session = self._sessions.get(
                session_id
            )

            if session is None:
                return []

            session["last_active"] = time.time()

            # Return a copy.
            return list(
                session["history"]
            )

    async def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str
    ):

        async with self._lock:

            session = self._sessions.get(
                session_id
            )

            if session is None:

                raise ValueError(
                    "Session does not exist."
                )

            session["history"].append(
                {
                    "role": "user",
                    "content": user_message,
                }
            )

            session["history"].append(
                {
                    "role": "assistant",
                    "content": assistant_message,
                }
            )

            session["last_active"] = time.time()

    async def get_session_lock(
        self,
        session_id: str
    ):

        async with self._lock:

            lock = self._session_locks.get(
                session_id
            )

            if lock is None:

                raise ValueError(
                    "Session does not exist."
                )

            return lock

    async def delete_session(
        self,
        session_id: str
    ) -> bool:

        async with self._lock:

            if session_id not in self._sessions:

                return False

            del self._sessions[session_id]

            self._session_locks.pop(
                session_id,
                None
            )

            self._request_timestamps.pop(
                session_id,
                None
            )

            return True

    async def cleanup_expired(self) -> int:

        current_time = time.time()

        removed = 0

        async with self._lock:

            expired_sessions = [
                session_id
                for session_id, session in self._sessions.items()
                if (
                    current_time
                    - session["last_active"]
                    > self.session_ttl_seconds
                )
            ]

            for session_id in expired_sessions:

                del self._sessions[session_id]

                self._session_locks.pop(
                    session_id,
                    None
                )

                self._request_timestamps.pop(
                    session_id,
                    None
                )

                removed += 1

        return removed

    async def session_count(self) -> int:

        async with self._lock:

            return len(
                self._sessions
            )