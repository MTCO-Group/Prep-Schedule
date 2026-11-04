r"""
GitHub App Token
Version 1.0

1.0: Nathan, 04/11/2026: the Prep Schedule app signs in to GitHub as the
MTCOautomations GitHub App (owned by MTCO-Group) instead of with a person's
token. The app's private key makes a short JWT, GitHub swaps that for an
installation token that lasts an hour, and this module asks for that token
for one repo with Contents write only. app.py keeps one of these per server
process (st.cache_resource), so the 10 second reruns never make a new token.

PyJWT is imported only when a token is first needed, so app.py still starts
(and falls back to GITHUB_TOKEN) on a server that has not installed it yet.
"""

import datetime
import threading
import time

import requests

API = "https://api.github.com"
JWT_BACKDATE_S = 60       # GitHub's advice: allow for clock drift
JWT_LIFETIME_S = 540      # GitHub allows at most 10 minutes
REFRESH_BEFORE_S = 300    # swap a token this long before it expires


class GitHubAppError(RuntimeError):
    """GitHub refused to issue an installation token."""


def normalise_key(text):
    """The PEM as GitHub issued it, also when pasted into a secret with
    literal \n sequences instead of line breaks."""
    text = (text or "").strip()
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    return text + "\n"


def _parse_time(stamp):
    return datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc).timestamp()


class GitHubAppAuth:
    """Installation tokens for one GitHub App installation, one repo, Contents write."""

    def __init__(self, app_id, installation_id, private_key, repo_name, post=None, clock=time.time):
        self.app_id = str(app_id).strip()
        self.installation_id = str(installation_id).strip()
        self.private_key = normalise_key(private_key)
        self.repo_name = repo_name
        self._post = post or requests.post
        self._clock = clock
        self._lock = threading.Lock()
        self._token = None
        self._expires = 0.0

    def app_jwt(self):
        import jwt  # PyJWT; see the module note
        now = int(self._clock())
        claims = {"iss": self.app_id, "iat": now - JWT_BACKDATE_S, "exp": now + JWT_LIFETIME_S}
        return jwt.encode(claims, self.private_key, algorithm="RS256")

    def token(self):
        with self._lock:
            if self._token and self._clock() < self._expires - REFRESH_BEFORE_S:
                return self._token
            r = self._post(
                f"{API}/app/installations/{self.installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {self.app_jwt()}",
                         "Accept": "application/vnd.github+json",
                         "User-Agent": "kensite-prep-schedule"},
                json={"repositories": [self.repo_name], "permissions": {"contents": "write"}},
                timeout=15,
            )
            if r.status_code != 201:
                try:
                    message = r.json().get("message", "")
                except ValueError:
                    message = ""
                raise GitHubAppError(f"GitHub App token refused: {r.status_code} {message}".strip())
            body = r.json()
            self._token = body["token"]
            self._expires = _parse_time(body["expires_at"])
            return self._token
