from abc import abstractmethod, ABC
from typing import Dict, Any


class HttpAuthenticator(ABC):
    @abstractmethod
    def get_auth_header(self) -> Dict[str, Any]:
        """
        :return: A dictionary containing all the necessary params to authenticate.
        """


class NoAuth(HttpAuthenticator):
    def get_auth_header(self) -> Dict[str, Any]:
        return {}
