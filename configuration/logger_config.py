import logging
from config import Config

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"{Config.LOG_FILENAME}.log", mode='w', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
