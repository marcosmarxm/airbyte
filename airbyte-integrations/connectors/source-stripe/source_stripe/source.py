from typing import Any, Mapping, Tuple, Dict, Union, Iterable

import requests
from base_python import AbstractSource, HttpAuthenticator, HttpStream, ResponseParser, Stream, SimpleAuthenticator


class StripeStream(HttpStream):
    url_base = "https://api.stripe.com/v1/"

    def get_next_page_token(self, decoded_response: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        if decoded_response['has_more'] and bool(decoded_response['has_more']):
            if decoded_response['data'] and len(decoded_response['data']) > 0:
                last_object_id = decoded_response['data'][-1]['id']
                return {'starting_after': last_object_id}

    def parse_response(self, decoded_response: Dict) -> Iterable[Dict]:
        yield from decoded_response['data']


class Charges(StripeStream):
    path = "charges"


class BalanceTransactions(StripeStream):
    name = "balance_transactions"
    path = "balance_transactions"

class CustomerBalanceTransactions:
    path = "customers/{customer_id}/customer_balance_transactions"

# Incremental

# Nested ??

class SourceStripe(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        # TODO
        return True, None

    def streams(self, config: Mapping[str, Any], **kwargs) -> Mapping[str, Stream]:
        authenticator = SimpleAuthenticator(config['client_secret'])

        return {
            "charges": Charges(authenticator=authenticator),
            "balance_transactions": BalanceTransactions(authenticator=authenticator)
        }
