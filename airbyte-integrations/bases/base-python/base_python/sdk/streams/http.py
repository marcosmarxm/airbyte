import copy
from abc import ABC, abstractmethod
from typing import Dict, Iterable, Any, Union, Optional

import requests

from ..auth.core import HttpAuthenticator, NoAuth

from .core import Stream


class HttpStream(Stream, ABC):

    def __init__(self, authenticator: HttpAuthenticator = NoAuth(), parent_stream: 'HttpStream' = None):
        self._authenticator = authenticator
        self._parent_stream = parent_stream
        self._session = requests.Session()

    @property
    @abstractmethod
    def url_base(self) -> str:
        """
        :return: URL base for the  API endpoint e.g: if you wanted to hit https://myapi.com/v1/some_entity then this should return "https://myapi.com/v1/"
        """

    @property
    def http_method(self) -> str:
        """
        Override if needed. See get_request_data if using POST.
        """
        return "GET"

    @property
    def authenticator(self) -> HttpAuthenticator:
        return self._authenticator

    def get_request_configurations(self, stream_state: Dict[str, Any], parent_stream_record: Dict = None) -> Iterable[Optional[Dict]]:
        """
        Override this method if you need to make multiple HTTP requests (not counting pagination) to fully read the data from this stream.
        For example, if each request reads data for a particular date and you want to read data from multiple dates, then this method should
        return one dict for each request that should be made e.g: [{'date':'01-01-2020'}, {'date':'01-02-2020'}], etc.

        Each request configurations will be passed input to most other methods in this class for use as needed.

        Note that pagination is handled separately. For instance, following the date example above, if you only need to query
        one date, but the response contains 10 pages (each of which creates an HTTP request), then this method should return an iterable with one
        element {'date':'01-01-2020'} and pagination should be handled separately through get_next_page_token.

        :return: An iterable (list or generator) of request configurations
        """
        return [None]

    @abstractmethod
    def get_next_page_token(self, decoded_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Override this method to define a pagination strategy.

        The value returned from this method is passed to most other methods in this class. Use it to form a request e.g: set headers or query params.

        :return: The token for the next page from the input response object. Returning None means there are no more pages to read in this response.
        """

    @abstractmethod
    def path(
            self,
            request_configuration: Optional[Dict] = None,
            stream_state: Dict[str, Any] = {},
            next_page_token: Dict[str, Any] = None,
            parent_stream_record: Dict = None
    ) -> str:
        """
        Returns the URL path for the API endpoint e.g: if you wanted to hit https://myapi.com/v1/some_entity then this should return "some_entity"
        """

    def get_request_params(
            self,
            request_configuration: Optional[Dict] = None,
            stream_state: Dict[str, Any] = {},
            next_page_token: Dict[str, Any] = None,
            parent_stream_record: Dict = None
    ) -> Dict[str, Any]:
        """
        Override this method to define the query parameters that should be set on an outgoing HTTP request given the inputs.

        E.g: you might want to define query parameters for paging if next_page_token is not None.
        """
        return {}

    def get_request_headers(
            self,
            request_configuration: Optional[Dict] = None,
            stream_state: Dict[str, Any] = {},
            next_page_token: Dict[str, Any] = None,
            parent_stream_record: Dict = None
    ) -> Dict[str, Any]:
        """
        Override to return any non-auth headers. Authentication headers will overwrite any overlapping headers returned from this method.
        """
        return {}

    def get_request_body_json(
            self,
            request_configuration: Optional[Dict] = None,
            stream_state: Dict[str, Any] = {},
            next_page_token: Dict[str, Any] = None,
            parent_stream_record: Dict = None
    ) -> Optional[Dict]:
        """
        TODO make this possible to do for non-JSON APIs
        Override when creating POST requests to populate the body of the request with a JSON payload.
        """
        return None

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
        of 100 responses. This is also useful if you want to transform the incoming data e.g: filter some records or change some fields.

        By default, this returns an iterable containing the input. Override to parse differently.
        :param response:
        :return: An iterable containing the parsed response
        """
        yield [response]

    # def backoff_time(self, response: requests.Response):
    #     """
    #     :return: How long to backoff for
    #     """
    #     # TODO
    #     return 1
    #
    # def should_backoff(self, response: requests.Response) -> bool:
    #     """
    #     Override to set different conditions for backoff.
    #     """
    #     return response.status_code == 429 or 500 <= response.status_code < 600

    def _create_prepared_request(self, path: str, headers: Dict = None, params: Dict = None, json: Any = None) -> requests.PreparedRequest:
        args = {
            'method': self.http_method,
            'url': self.url_base + path,
            'headers': headers,
            'params': params
        }

        if self.http_method.upper() == "POST":
            args['body'] = json

        return requests.Request(**args).prepare()

    def _send_request(self, request: requests.PreparedRequest) -> requests.Response:
        # TODO handle errors, rate limits
        return self._session.send(request)

    def _list_records(self, stream_state: Dict[str, Any] = {}, parent_stream_record: Dict[str, Any] = None) -> Iterable[Dict[str, Any]]:
        """
        :param parent_stream_record If this is a child stream, this is a record from the parent stream. Otherwise, this record is None.
        :return:
        """

        args = {'stream_state': stream_state}
        if parent_stream_record:
            args['parent_stream_record'] = parent_stream_record

        for request_configuration in self.get_request_configurations(**copy.deepcopy(args)):
            args['request_configuration'] = request_configuration
            pagination_complete = False

            while not pagination_complete:
                request = self._create_prepared_request(
                    path=self.path(**args),
                    headers=dict(self.get_request_headers(**args), **self.authenticator.get_auth_header()),
                    params=self.get_request_params(**args),
                    json=self.get_request_body_json(**args)
                )

                response = self._send_request(request)

                decoded_response = self.decode_response(response)
                yield from self.parse_response(decoded_response)

                next_page_token = self.get_next_page_token(decoded_response)
                if next_page_token:
                    args['next_page_token'] = next_page_token
                else:
                    pagination_complete = True

        # Always return an empty generator just in case no records were ever yielded
        yield from []

    def read_stream(self, stream_state: Dict[str, Any] = None) -> Iterable[Dict[str, Any]]:
        # TODO this can be made more efficient if syncs are sequenced so that each API endpoint is called exactly once. Right now parent streams are
        # re-read for the benefit of syncing the child stream.
        if self._parent_stream:
            for parent_stream_record in self._parent_stream.read_stream():
                yield from self._list_records(parent_stream_record=parent_stream_record, stream_state=stream_state)
        else:
            yield from self._list_records(stream_state=stream_state)
