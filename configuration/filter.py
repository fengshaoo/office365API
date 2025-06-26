import logging


class NoParamsFilter(logging.Filter):
    """
    过滤掉包含特定关键词的 SQLAlchemy 日志行
    """
    FILTER_KEYWORDS = [
        'parameters',
        '[generated in',
        '[cached since',
    ]

    def filter(self, record):
        msg = record.getMessage().lower()
        return not any(keyword in msg for keyword in self.FILTER_KEYWORDS)