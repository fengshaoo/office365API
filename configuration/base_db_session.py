import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url
from contextlib import contextmanager

from config import Config
from errorInfo import BasicException, ErrorCode

SENSITIVE_KEYS = {"access_token", "refresh_token", "password", "secret"}

def sanitize_params(params: dict):
    if not isinstance(params, dict):
        return {}
    return {
        k: "<sensitive>" if k in SENSITIVE_KEYS else v
        for k, v in params.items()
    }

class BaseDBSession:
    _engine = None
    _SessionFactory = None

    def __init__(self, database_url: str = None):
        if not BaseDBSession._engine:
            database_url = database_url or Config.DATABASE_URL
            db_url = make_url(f"mysql+pymysql://{database_url}")
            BaseDBSession._engine = create_engine(
                db_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=1800,

                # TODO 其他地方配合该处隐藏参数
                hide_parameters=True
            )
            BaseDBSession._SessionFactory = sessionmaker(bind=BaseDBSession._engine)

    @classmethod
    def keep_alive(cls):
        logging.info("数据库保活")
        try:
            session = cls._SessionFactory()
            session.execute(text("SELECT 1"))
        except Exception as e:
            raise BasicException(ErrorCode.DB_ERROR, extra=e)


    @contextmanager
    def get_session(self):
        session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            sanitized = {}
            if hasattr(e, 'params'):
                sanitized = sanitize_params(e.params)
            logging.error(f"数据库异常（敏感参数已隐藏）: {e.__class__.__name__} - {sanitized}")
            raise BasicException(ErrorCode.DB_ERROR, extra=e)
        except Exception as e:
            session.rollback()
            raise BasicException(ErrorCode.DB_ERROR, extra=e)
        finally:
            session.close()