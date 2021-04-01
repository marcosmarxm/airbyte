from typing import Mapping, Any

from base_python.sdk.streams.auth.core import HttpAuthenticator

class ApiTokenAuthenticator(HttpAuthenticator):
    def __init__(self, token: str):
        self._token = token

    def get_auth_header(self) -> Mapping[str, Any]:
        return {"Authorization": f"Bearer {self._token}"}
