import logging


class NoParamsFilter(logging.Filter):
    """
    禁止SQL输出参数
    """
    def filter(self, record):
        # return 'parameters' not in record.getMessage().lower()

        return not isinstance(record.args, dict)