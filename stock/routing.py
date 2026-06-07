from django.urls import re_path
from .consumers import StockConsumer, TransactionConsumer, CustomerConsumer

websocket_urlpatterns = [
    re_path(r'ws/stock/$', StockConsumer.as_asgi()),
    re_path(r'ws/transaction/$', TransactionConsumer.as_asgi()),
    re_path(r'ws/customer/$', CustomerConsumer.as_asgi()),
]