from abc import ABC, abstractmethod
from typing import Dict, Iterable, Any, Union

import requests

from ..auth.core import HttpAuthenticator, NoAuth
from .core import Stream

class HttpStream(Stream, ABC):
    http_method = "GET"

    def __init__(self, authenticator: HttpAuthenticator = NoAuth(), parent_stream: 'HttpStream' = None):
        self._authenticator = authenticator
        self._parent_stream = parent_stream

    @property
    def authenticator(self) -> HttpAuthenticator:
        return self._authenticator

    def decode_response(self, response: requests.Response) -> Dict:
        """
        Decodes the response object from its raw form returned from the API to a Dict. By default this parses a JSON.
        Override to parse responses differently e.g as XML or custom binary format.

        :param response: The response object returned from the API endpoint.
        :return: The response object decoded into a Dict. For example, using response.json() or response.text() wrapped in a Dict etc...
        """
        return response.json()

    def parse_response(self, response: Dict) -> Iterable[Dict]:
        """
        Parses the raw response object into a list of records. This is useful in cases where a response contains more than one record e.g: a page
        of 100 responses. This is also useful

        By default, this returns an iterable containing the input. Override to parse differently.
        :param response:
        :return: An iterable containing the parsed response
        """
        yield [response]

    @abstractmethod
    def get_next_page_token(self, response: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        """
        Override this method to define a pagination strategy.

        :return: The token for the next page from the input response object. Returning None means there are no more pages to read in this response.
        """

    def get_request_params(self, stream_state: Dict[str, Any] = {}, parent_stream_record: Dict = None) -> Iterable[Dict[str, Any]]:
        """
        :return: An iterable of request parameters. Each dict returned will be used to make a request (with pagination).
        If you need to make multiple requests (not including pagination) to read this stream (for example, if each request reads data for a particular
        date and you want to read data from multiple dates), then this method should return one dict for each request e.g: for each date.
        """
        yield from [{}]

    @property
    @abstractmethod
    def url_base(self) -> str:
        """
        :return: URL base for the  API endpoint e.g: if you wanted to hit https://myapi.com/v1/some_entity then this should return "https://myapi.com/v1/"
        """

    @abstractmethod
    def path(self, stream_state: Dict[str, Any] = {}, parent_stream_record: Dict = None) -> str:
        """
        :param parent_stream_record If this is a child stream, this is a record from the parent stream. Otherwise, this is None.
        :return: URL path for the API endpoint e.g: if you wanted to hit https://myapi.com/v1/some_entity then this should return "some_entity"
        """

    def list_records(self, stream_state: Dict[str, Any] = {}, parent_stream_record: Dict[str, Any] = None) -> Iterable[Dict[str, Any]]:
        """
        :param parent_stream_record If this is a child stream, this is a record from the parent stream. Otherwise, this record is None.
        :return:
        """
        # create empty request
        args = {'parent_stream_record': parent_stream_record} if parent_stream_record else {'stream_state': stream_state}

        request_parameters = self.get_request_params(**args) or [{}]
        for params in request_parameters:
            done = False
            # while loop paginates through the response
            while not done:
                request = requests.Request(
                    method=self.http_method,
                    url=self.url_base + self.path(**args),
                    headers=self.authenticator.get_auth_header(),
                    params=params
                )

                # TODO handle errors, rate limits
                response = requests.Session().send(request.prepare())
                decoded_response = self.decode_response(response)
                yield from self.parse_response(decoded_response)
                next_page_token = self.get_next_page_token(decoded_response)
                if next_page_token:
                    params.update(next_page_token)
                else:
                    done = True

        # Always return an empty generator just in case no records were ever yielded
        yield from []

    def read_stream(self, stream_state: Dict[str, Any] = None) -> Iterable[Dict[str, Any]]:
        # TODO this can be made more efficient if syncs are sequenced so that each API endpoint is called exactly once. Right now parent streams are
        # re-read for the benefit of syncing the child stream.
        if self._parent_stream:
            for parent_stream_record in self._parent_stream.read_stream():
                yield from self.list_records(parent_stream_record=parent_stream_record)
        else:
            yield from self.list_records(stream_state=stream_state)
