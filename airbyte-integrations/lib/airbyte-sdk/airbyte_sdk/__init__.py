from abc import ABC, abstractmethod
from typing import Dict, Callable, Tuple
import requests
from requests import Response


class HttpApiClient(ABC):
    @property
    @abstractmethod
    def url_base(self) -> str:

    def response_decoder(self) -> Callable[[Response], Dict]:
        """
        :return: A function which converts the . By default, this is a JSON parser. Override if your response takes a different format.
        """
        def parser(response: Response):
            return response.json()

        return parser

    @abstractmethod
    def get_next_page(self) -> Tuple[str, Dict]:
        """
        :return:r
        """

    @abstractmethod
    def get(self, relative_path: str, params: Dict) -> Dict:
        """
        :return: Raw response
        """
        path = f"{self.url_base}/{relative_path}"
        return requests.get(path, params).json()


class HTTPStream(ABC):
    pass
