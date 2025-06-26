import copy

import requests

from config import Config


class CustomSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.default_headers = copy.deepcopy(Config.REQUEST_COMMON_HEADERS)

    def request(self, method, url, **kwargs):

        proxy = kwargs.pop('proxy', None)
        headers = kwargs.pop('headers', {})
        # 合并 headers：优先使用调用方传入的 headers
        final_headers = copy.deepcopy(self.default_headers)
        final_headers.update(headers)
        kwargs['headers'] = final_headers

        # 自动注入代理
        if proxy:
            kwargs.setdefault('proxies', {
                'http': proxy,
                'https': proxy
            })

        return super().request(method, url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)