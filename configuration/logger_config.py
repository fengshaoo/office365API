import logging
from config import Config


class NoParamsFilter(logging.Filter):
    def filter(self, record):
        return 'parameters' not in record.getMessage().lower()

class CLogger(object):
    _initialized = False

    @classmethod
    def setup_logger(cls):
        if cls._initialized:
            return
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{Config.LOG_FILENAME}.log", mode='w', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logging.info("日志初始化配置完成")
        cls._initialized = True
