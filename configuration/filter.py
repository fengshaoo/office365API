import logging


class NoParamsFilter(logging.Filter):
    """
    禁止SQL输出参数
    """
    def filter(self, record):
        msg = record.getMessage().lower()
        if 'parameters' in msg:
            return False
        if msg.startswith("[generated in"):
            return False
        return True