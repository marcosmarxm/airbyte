from abc import ABC, abstractmethod
from typing import Any, Mapping, Tuple, Dict, Union, Iterable

import requests
from base_python import AbstractSource, HttpAuthenticator, HttpStream, IncrementalStream, Stream, SimpleAuthenticator


class StripeStream(HttpStream):
    url_base = "https://api.stripe.com/v1/"

    def get_next_page_token(self, decoded_response: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        logger.info("Hey there partner!!!")
        # if decoded_response['has_more'] and bool(decoded_response['has_more']):
        #     if decoded_response['data'] and len(decoded_response['data']) > 0:
        #         last_object_id = decoded_response['data'][-1]['id']
        #         return {'starting_after': last_object_id}
        return None  # skip for faster testing

    def parse_response(self, decoded_response: Dict) -> Iterable[Dict]:
        if decoded_response['data']:
            for record in decoded_response['data']:
                yield record

    def get_request_params(self, **kwargs):
        # TODO remove this limit. just here to speed up testing
        return {'limit': 1}


class IncrementalStripeStream(StripeStream, IncrementalStream, ABC):
    continuously_save_state = False  # Stripe returns most recently created objects first :(

    @property
    @abstractmethod
    def cursor_field(self) -> str:
        pass

    def get_request_params(self, stream_state=None, **kwargs):
        stream_state = stream_state or {}
        params = super().get_request_params(stream_state=stream_state)
        params.update({
            'created': stream_state.get(self.cursor_field)
        })
        return params

    def get_updated_state(self, current_state, latest_record) -> Dict[str, Any]:
        return {
            self.cursor_field: max(latest_record.get(self.cursor_field), current_state.get(self.cursor_field, 0))
        }


class Customers(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs) -> str:
        return "customers"


class BalanceTransactions(IncrementalStripeStream):
    cursor_field = 'created'
    name = "balance_transactions"

    def path(self, **kwargs) -> str:
        return "balance_transactions"


class Charges(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs) -> str:
        return "charges"


class CustomerBalanceTransactions(StripeStream):
    name = "customer_balance_transactions"

    def path(self, parent_stream_record, **kwargs):
        customer_id = parent_stream_record['id']
        return f"customers/{customer_id}/balance_transactions"


class Coupons(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "coupons"


class Disputes(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "disputes"


class Events(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "events"


class Invoices(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "invoices"


class InvoiceLineItems(StripeStream):
    name = 'invoice_line_items'

    def path(self, parent_stream_record, **kwargs):
        return f"invoices/{parent_stream_record['id']}/lines"


class InvoiceItems(IncrementalStripeStream):
    cursor_field = 'date'
    name = 'invoice_items'

    def path(self, **kwargs):
        return "invoiceitems"


class Payouts(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "payouts"


class Plans(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "plans"


class Products(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "products"


class Subscriptions(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "subscriptions"


class SubscriptionItems(StripeStream):
    name = 'subscription_items'

    def path(self, parent_stream_record, **kwargs):
        return "subscription_items"

    # TODO we should pack state and everything else into a context object?
    def get_request_params(self, parent_stream_record=None, **kwargs):
        params = super().get_request_params()
        params['subscription'] = parent_stream_record['id']
        return params


class Transfers(IncrementalStripeStream):
    cursor_field = 'created'

    def path(self, **kwargs):
        return "transfers"


class SourceStripe(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        # TODO
        return True, None

    def streams(self, config: Mapping[str, Any]) -> Mapping[str, Stream]:
        authenticator = SimpleAuthenticator(config['client_secret'])

        customers = Customers(authenticator=authenticator)
        subscriptions = Subscriptions(authenticator=authenticator)
        invoices = Invoices(authenticator=authenticator)
        return {
            "balance_transactions": BalanceTransactions(authenticator=authenticator),
            "charges": Charges(authenticator=authenticator),
            "coupons": Coupons(authenticator=authenticator),
            "customers": customers,
            "customer_balance_transactions": CustomerBalanceTransactions(authenticator=authenticator, parent_stream=customers),
            "disputes": Disputes(authenticator=authenticator),
            "events": Events(authenticator=authenticator),
            "invoice_items": InvoiceItems(authenticator=authenticator),
            "invoice_line_items": InvoiceLineItems(authenticator=authenticator, parent_stream=invoices),
            "invoices": invoices,
            "plans": Plans(authenticator=authenticator),
            "payouts": Payouts(authenticator=authenticator),
            "products": Products(authenticator=authenticator),
            "subscriptions": subscriptions,
            "subscription_items": SubscriptionItems(authenticator=authenticator, parent_stream=subscriptions),
            "transfers": Transfers(authenticator=authenticator)
        }
