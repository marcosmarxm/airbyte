from requests import exceptions


class BaseBackoffException(exceptions.HTTPError):
    pass


class CustomBackoffException(BaseBackoffException):
    """
    An exception that exposes how long it attempted to backoff
    """

    def __init__(self, backoff, request, response):
        self.backoff = backoff
        super().__init__(request=request, response=response)


class DefaultBackoffException(BaseBackoffException):
    pass
