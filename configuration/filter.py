import logging


class NoParamsFilter(logging.Filter):
    """
    禁止SQL输出参数
    """
    def filter(self, record):
        msg = record.getMessage().lower()
        logging.error(msg)
        if 'parameters' in msg or 'generated in' in msg:
            return False
        return True