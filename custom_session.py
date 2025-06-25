import copy

import requests

from config import Config


class CustomSession(requests.Session):
    def __init__(self, proxy=None, user_agent=None):
        super().__init__()
        self.headers = copy.deepcopy(Config.REQUEST_COMMON_HEADERS)

    def request(self, method, url, **kwargs):
        proxy = kwargs.pop('proxy', None)
        user_agent = kwargs.pop('user_agent', None)
        # 自动注入代理
        if proxy:
            kwargs.setdefault('proxies', {
                'http': proxy,
                'https': proxy
            })

        # 自动注入 User-Agent
        if user_agent:
            self.headers['User-Agent'] = user_agent
        else:
            self.headers.pop("User-Agent", None)  # 若无则移除，避免发送空字符串

        return super().request(method, url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)