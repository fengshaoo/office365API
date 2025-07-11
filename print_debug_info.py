import logging


class PrintDebugInfo:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def print_request_debug(self, response):
        self.logger.info(f"[REQUEST] {response.request.method} {response.request.url}")
        self.logger.info(f"[HEADERS] {response.request.headers}")
        self.logger.info(f"[BODY] {response.request.body}")
        self.logger.info(f"[STATUS] {response.status_code}")
        self.logger.info(f"[RESPONSE] {response.text}")