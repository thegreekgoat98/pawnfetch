from __future__ import annotations

import httpx

from pawnfetch.models import PlayerProfile, PlayerStats

BASE_URL = "https://api.chess.com/pub"
USER_AGENT = "pawnfetch-cli (contact: your-email@example.com)"


class ChessComError(Exception):
    """Base exception for all pawnfetch client errors."""


class PlayerNotFoundError(ChessComError):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"No chess.com player found with username '{username}'.")


class ChessComConnectionError(ChessComError):
    """Raised when pawnfetch can't reach chess.com at all."""


class ChessComRateLimitError(ChessComError):
    """Raised when chess.com returns 429 Too Many Requests."""


class ChessComServerError(ChessComError):
    """Raised on unexpected 5xx/other errors from chess.com."""


class ChessComClient:
    def __init__(self, timeout: float = 10.0):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )

    def get_profile(self, username: str) -> PlayerProfile:
        data = self._get(f"/player/{username.strip().lower()}")
        return PlayerProfile.from_api(data)

    def get_stats(self, username: str) -> PlayerStats:
        data = self._get(f"/player/{username.strip().lower()}/stats")
        return PlayerStats.from_api(username, data)

    def _get(self, path: str) -> dict:
        try:
            response = self._client.get(f"{BASE_URL}{path}")
        except httpx.ConnectError as exc:
            raise ChessComConnectionError(
                "Couldn't reach chess.com. Check your internet connection."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ChessComConnectionError(
                "Request to chess.com timed out. Try again."
            ) from exc

        if response.status_code == 404:
            username = path.split("/")[2]
            raise PlayerNotFoundError(username)
        if response.status_code == 429:
            raise ChessComRateLimitError(
                "chess.com rate-limited this request. Wait a moment and try again."
            )
        if response.status_code >= 500:
            raise ChessComServerError(
                f"chess.com returned a server error ({response.status_code}). Try again later."
            )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ChessComClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()