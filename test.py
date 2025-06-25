import copy

import requests

from config import Config

class CSession(requests.Session):
    def __init__(self, proxy=None, user_agent=None):
        super().__init__()
        self.headers = copy.deepcopy(Config.REQUEST_COMMON_HEADERS)

    def request(self, method, url, **kwargs):

        return super().request(method, url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)



def getmstoken(client_id, client_secret, refresh_token, proxy, user_agent):
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
        "scope": "https://graph.microsoft.com/.default"
    }

    session = CSession()

    resp = session.post(Config.ACCESS_TOKEN_URI,data=data,timeout=10,)
    print(resp.text)

def rua():
    url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    data = {
        "client_id": "你的client_id",
        "client_secret": "你的client_secret",
        "grant_type": "refresh_token",
        "refresh_token": "你的refresh_token",
        "scope": "https://graph.microsoft.com/.default"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    resp = requests.post(url, data=data, headers=headers)
    print(resp.request.headers)
    print(resp.json())

if __name__ == "__main__":
    getmstoken("aaa", "bbb", "ccc", None, None)
