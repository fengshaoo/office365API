import logging
from config import Config
from configuration.filter import NoParamsFilter


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
                # logging.StreamHandler()
            ]
        )
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.addFilter(NoParamsFilter())
        logging.info("日志初始化配置完成")
        cls._initialized = True
