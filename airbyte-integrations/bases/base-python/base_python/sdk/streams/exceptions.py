import requests


class BaseBackoffException(requests.exceptions.HTTPError):
    pass


class CustomBackoffException(BaseBackoffException):
    """
    A class that specifies how long to backoff
    """

    def __init__(self, backoff: int, request: requests.PreparedRequest, response: requests.Response):
        """
        :param backoff: how long to backoff in seconds
        :param request: the request that triggered this backoff exception
        :param response: the response that triggered the backoff exception
        """
        self.backoff = backoff
        super().__init__(request=request, response=response)


class DefaultBackoffException(BaseBackoffException):
    pass
