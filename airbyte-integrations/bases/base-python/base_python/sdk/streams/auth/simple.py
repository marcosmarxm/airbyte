from typing import Dict, Any

from .core import HttpAuthenticator

class SimpleAuthenticator(HttpAuthenticator):
    def __init__(self, token: str):
        self._token = token

    def get_auth_header(self) -> Dict[str, Any]:
        return {"Authorization": f"Bearer {self._token}"}
