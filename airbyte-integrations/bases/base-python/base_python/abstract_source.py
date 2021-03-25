"""
MIT License

Copyright (c) 2020 Airbyte

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import copy
import inspect
from datetime import datetime
from typing import Any, Iterator, Mapping, MutableMapping, Type, Tuple, Generator, Dict, Callable, Union, Iterable
from abc import ABC, abstractmethod

import requests
from airbyte_protocol import (
    AirbyteCatalog,
    AirbyteConnectionStatus,
    AirbyteMessage,
    AirbyteRecordMessage,
    AirbyteStateMessage,
    ConfiguredAirbyteCatalog,
    ConfiguredAirbyteStream,
    Status,
    SyncMode, AirbyteStream,
)
from airbyte_protocol import Type as MessageType

from .client import BaseClient
from .integration import Source
from .schema_helpers import ResourceSchemaLoader
from .logger import AirbyteLogger


#
# class IncrementalStreamMixin:
#
#     @abstractmethod
#     def get_stream_state(self) -> Any:
#         """Get state of stream with corresponding name"""
#         raise NotImplementedError
#
#     @abstractmethod
#     def set_stream_state(self, name: str, state: Any):
#         """Set state of stream with corresponding name"""
#         raise NotImplementedError
#
#

def package_name_from_class(cls: object) -> str:
    """Find the package name given a class name"""
    module = inspect.getmodule(cls)
    return module.__name__.split(".")[0]


class Stream(ABC):
    @property
    def name(self) -> str:
        """
        :return: Stream name. By default this is the implementing class name, but it can be overridden as needed.
        """
        return self.__class__.__name__

    @abstractmethod
    def read_stream(self, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        :return: A generator which yields all the records in this stream. This method should be overridden by subclasses
        """

    def get_json_schema(self) -> Dict[str, Any]:
        """
        :return: A dict of the JSON schema representing this stream.

        The default implementation of this method looks for a JSONSchema file with the same name as this stream's "name" property
        """
        # TODO change to snakecase by default
        return ResourceSchemaLoader(package_name_from_class(self.__class__)).get_schema(self.name)

    # TODO add children streams


class HttpAuthenticator(ABC):
    @abstractmethod
    def get_auth_header(self) -> Dict[str, Any]:
        """
        :return: A dictionary containing all the necessary params to authenticate.
        """


class NoAuth(HttpAuthenticator):
    def get_auth_header(self) -> Dict[str, Any]:
        return {}


class SimpleAuthenticator(HttpAuthenticator):
    def __init__(self, token: str):
        self._token = token

    def get_auth_header(self) -> Dict[str, Any]:
        return {"Authorization": f"Bearer {self._token}"}


class JWTAuthenticator(HttpAuthenticator):
    def get_auth_header(self) -> Dict[str, Any]:
        # TODO
        raise NotImplementedError


class Oauth2Authenticator(HttpAuthenticator):
    def get_auth_header(self) -> Dict[str, Any]:
        # TODO
        raise NotImplementedError


class ResponseDecoder(ABC):
    @abstractmethod
    def decode(self, response: requests.Response) -> Dict:
        """
        :param response:
        :return:
        """


class JsonDecoder(ResponseDecoder):
    def decode(self, response: requests.Response) -> Dict:
        return response.json()


class ResponseParser(ABC):
    @abstractmethod
    def parse(self, response: Dict) -> Iterable[Any]:
        """
        :param response:
        :return:
        """


class ExactResponse(ResponseParser):
    def parse(self, response: Dict) -> Iterable[Any]:
        yield [response]


class HttpStream(Stream, ABC):
    http_method = "GET"

    def __init__(self, authenticator: HttpAuthenticator = NoAuth()):
        self._authenticator = authenticator

    @property
    def authenticator(self) -> HttpAuthenticator:
        return self._authenticator

    def decode_response(self, response: requests.Response) -> Dict:
        """
        Decodes the response object from its raw form returned from the API to a Dict. By default this parses a JSON.
        Override to parse responses differently.

        :param response: The response object returned from the API endpoint.
        :return: The response object decoded into a Dict. For example, using response.json() or response.text() wrapped in a Dict etc...
        """
        return response.json()

    def parse_response(self, response: Dict) -> Iterable[Dict]:
        """
        Parses the raw response object into a list of records. This is useful in cases where a response contains more than one record e.g: a page
        of 100 responses. This is also useful

        By default, this returns an array containing just the decoded response dict. Override to parse differently.
        :param response:
        :return:
        """
        yield [response]

    #
    # @property
    # @abstractmethod
    # def get_iterator(self):
    #

    @abstractmethod
    def get_next_page_token(self, response: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        """
        :return: The token for the next page from the input response object. If None is returned, it is assumed that we are done reading this
        stream.
        """

    def get_request_params(self) -> Iterable[Dict[str, Any]]:
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
        :return: URL base for the API
        """

    @property
    @abstractmethod
    def path(self) -> str:
        """
        # TODO how would this deal with nested endpoints?
        :return: Relative URL for the API endpoint
        """

    def read_stream(self, **kwargs) -> Generator[Dict[str, Any], None, None]:
        # create empty request
        for request_params in self.get_request_params():
            done = False
            params = request_params
            while not done:
                request = requests.Request(
                    method=self.http_method,
                    url=self.url_base + self.path,
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


# Example of a class that can eventually be configured dynamically or via YAML
# class ComposableStream(Stream):
#     def __init__(self, read: Callable, get_json_schema: Callable):
#         self._read = read
#         self._get_json_schema = get_json_schema
#
#     def read(self, **kwargs) -> Generator[Dict[str, Any], None, None]:
#         return self._read(**kwargs)
#
#     def get_json_schema(self) -> Dict[str, Any]:
#         return self._get_json_schema()

class AbstractSource(Source, ABC):
    def __init__(self, schema_loader=None):
        super().__init__()
        self._schema_loader = schema_loader or ResourceSchemaLoader(package_name_from_class(self.__class__))

    @abstractmethod
    def check_connection(self, logger: AirbyteLogger, config: Mapping[str, Any]) -> Tuple[bool, Any]:
        """
        :return: A tuple of (boolean, error). If boolean is true, then we can connect to the underlying data source using the provided configuration.
        Otherwise, the input config cannot be used to connect to the underlying data source, and the "error" object should describe what went wrong.
        The error object will be cast to string to display the problem to the user.
        """

    @abstractmethod
    def streams(self, config: Mapping[str, Any] = None) -> Mapping[str, Stream]:
        """
        :return: A mapping from stream name to the stream class representing that stream
        """

    @property
    def name(self) -> str:
        """Source name"""
        return self.__class__.__name__

    def discover(self, logger: AirbyteLogger, config: Mapping[str, Any]) -> AirbyteCatalog:
        """Discover streams"""
        streams = []

        for name, stream in self.streams(config=config).items():
            supported_sync_modes = [SyncMode.full_refresh]
            # source_defined_cursor = False
            # if self.stream_has_state(name):
            #     supported_sync_modes = [SyncMode.incremental]
            #     source_defined_cursor = True

            streams.append(AirbyteStream(
                name=name,
                json_schema=stream.get_json_schema(),
                supported_sync_modes=supported_sync_modes,
                # source_defined_cursor=source_defined_cursor,
            ))

        return AirbyteCatalog(streams=streams)

    def check(self, logger: AirbyteLogger, config: Mapping[str, Any]) -> AirbyteConnectionStatus:
        """Check connection"""
        alive, error = self.health_check(logger, config)
        if not alive:
            return AirbyteConnectionStatus(status=Status.FAILED, message=str(error))

        return AirbyteConnectionStatus(status=Status.SUCCEEDED)

    def read(
            self, logger: AirbyteLogger, config: Mapping[str, Any], catalog: ConfiguredAirbyteCatalog, state: MutableMapping[str, Any] = None
    ) -> Iterator[AirbyteMessage]:

        state = state or {}
        total_state = copy.deepcopy(state)
        logger.info(f"Starting syncing {self.name}")
        for configured_stream in catalog.streams:
            try:
                yield from self._read_stream(logger=logger, config=config, configured_stream=configured_stream, state=total_state)
            except Exception as e:
                logger.exception(f"Encountered an exception while reading stream {self.name}")
                raise e

        logger.info(f"Finished syncing {self.name}")

    def _read_stream(
            self, logger: AirbyteLogger, config: Mapping[str, Any], configured_stream: ConfiguredAirbyteStream, state: MutableMapping[str, Any]
    ):
        stream_name = configured_stream.stream.name
        stream_instance = self.streams(config)[stream_name]
        # use_incremental = configured_stream.sync_mode == SyncMode.incremental and client.stream_has_state(stream_name)

        # if use_incremental and state.get(stream_name):
        #     logger.info(f"Set state of {stream_name} stream to {state.get(stream_name)}")
        #     client.set_stream_state(stream_name, state.get(stream_name))

        logger.info(f"Syncing {stream_name} stream")
        for record in stream_instance.read_stream():
            now = int(datetime.now().timestamp()) * 1000
            message = AirbyteRecordMessage(stream=stream_name, data=record, emitted_at=now)
            yield AirbyteMessage(type=MessageType.RECORD, record=message)

        # if use_incremental and client.get_stream_state(stream_name):
        #     # TODO this will need to be changed to allow efficient interleaved queries between child/parent streams
        #     state[stream_name] = client.get_stream_state(stream_name)
        #     # output state object only together with other stream states
        #     yield AirbyteMessage(type=MessageType.STATE, state=AirbyteStateMessage(data=state))
