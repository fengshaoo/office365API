import logging


class PrintDebugInfo:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def print_request_debug(self, response):
        self.logger.debug(f"[REQUEST] {response.request.method} {response.request.url}")
        self.logger.debug(f"[HEADERS] {response.request.headers}")
        self.logger.debug(f"[BODY] {response.request.body}")
        self.logger.debug(f"[STATUS] {response.status_code}")
        self.logger.debug(f"[RESPONSE] {response.text}")