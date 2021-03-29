from typing import Dict, Any

from .core import HttpAuthenticator

class JWTAuthenticator(HttpAuthenticator):
    def get_auth_header(self) -> Dict[str, Any]:
        # TODO
        raise NotImplementedError
