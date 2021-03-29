from typing import Dict, Any

from .core import HttpAuthenticator


class Oauth2Authenticator(HttpAuthenticator):
    def get_auth_header(self) -> Dict[str, Any]:
        # TODO
        raise NotImplementedError
