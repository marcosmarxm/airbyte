import inspect
from abc import ABC, abstractmethod
from typing import Dict, Any, Iterable
from ...logger import AirbyteLogger
from ...schema_helpers import ResourceSchemaLoader


def package_name_from_class(cls: object) -> str:
    """Find the package name given a class name"""
    module = inspect.getmodule(cls)
    return module.__name__.split(".")[0]


class Stream(ABC):
    logger = AirbyteLogger()  # TODO use native "logging" loggers with custom handlers

    @property
    def name(self) -> str:
        """
        :return: Stream name. By default this is the implementing class name, but it can be overridden as needed.
        """
        return self.__class__.__name__

    @abstractmethod
    def read_stream(self, stream_state: Dict[str, Any] = {}) -> Iterable[Dict[str, Any]]:
        """
        This method should be overridden by subclasses

        :param stream_state: State dict to use when extracting records.
        :return: A generator which yields all the records in this stream. Each record is a dict from properties to their values matching the schema
         of the stream.
        """

    def get_json_schema(self) -> Dict[str, Any]:
        """
        :return: A dict of the JSON schema representing this stream.

        The default implementation of this method looks for a JSONSchema file with the same name as this stream's "name" property.
        Override as needed.
        """
        # TODO show an example of using pydantic to define the JSON schema, or reading an OpenAPI spec
        # TODO change to snakecase by default
        return ResourceSchemaLoader(package_name_from_class(self.__class__)).get_schema(self.name)


class IncrementalStream(Stream, ABC):
    # TODO implement this to support fully auto-generating catalog info
    # @property
    # def cursor_field(self) -> str:
    #     """
    #     Override to return the name of the default cursor field used by this stream e.g: an API entity might always use created_at as the cursor field.
    #     :return: The name of the field used as a cursor
    #     """
    #     return []
    #
    # @property
    # @abstractmethod
    # def source_defined_cursor(self) -> bool:

    @property
    @abstractmethod
    def continuously_save_state(self) -> bool:
        """
        Decides whether state is always safe to checkpoint/save at any point.

        If set to true, a state message is output periodically while syncing this stream (which indicates to the process reading from this stream that
        state should be saved). If set to false, a state message is output only after the stream has been fully read.

        When possible, set this to true as it maximizes the efficiency of reading this stream. For example, if a sync fails halfway through, setting
        this flag to true will make the stream to read from the latest state. Setting it to false will make it re-extract all the records
        during the failed sync.

        This flag should only be set to false if records returned from the underlying data source are not returned in ascending order with respect
        to the cursor field e.g: if the source does not support reading records in ascending order of created_at date. In those cases, state must
        only be saved once the full stream has been read, and so this flag should be set to false.
        """

    @abstractmethod
    def get_updated_state(self, current_state: Dict[str, Any], latest_record: Dict):
        """
        Inspect the latest record extracted from the data source and the current state object and return an updated state object.
        It is safe to mutate the input state object and return it.

        For example: if the state object is based on created_at timestamp, and the current state is {'created_at': 10}, and the latest_record is
        {'name': 'octavia', 'created_at': 20 } then this method would return {'created_at': 20} to indicate state should be updated to this object.

        :param current_state: The stream's current state object
        :param latest_record: The latest record extracted from the stream
        :return: An updated state object
        """
