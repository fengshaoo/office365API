import logging

from sqlalchemy import create_engine, text, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url
from contextlib import contextmanager

from config import Config
from errorInfo import BasicException, ErrorCode


class BaseDBSession:
    _engine = None
    _SessionFactory = None

    def __init__(self, database_url: str = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        if not BaseDBSession._engine:
            database_url = database_url or Config.DATABASE_URL
            db_url = make_url(f"mysql+pymysql://{database_url}")
            BaseDBSession._engine = create_engine(
                db_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=1800,

                echo=False,
                hide_parameters=Config.HIDE_SQL_PARAMETERS
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
            self._log_sql_error(e)
            raise BasicException(ErrorCode.DB_ERROR, extra=e)
        except Exception as e:
            session.rollback()
            raise BasicException(ErrorCode.DB_ERROR, extra=e)
        finally:
            session.close()

    @contextmanager
    def get_readonly_session(self):
        """只读会话优化版"""
        session = self._SessionFactory()
        try:
            # 设置只读模式
            session.execute(text("SET TRANSACTION READ ONLY"))
            yield session
            # 只读会话不需要commit
        except SQLAlchemyError as e:
            session.rollback()
            self._log_sql_error(e)
            raise BasicException(ErrorCode.DB_ERROR, extra=e)
        except Exception as e:
            session.rollback()
            logging.error("Unexpected database error", exc_info=True)
            raise BasicException(ErrorCode.DB_ERROR, extra=e)
        finally:
            session.close()

    def _log_sql_error(self, error: SQLAlchemyError):
        """统一的SQL错误日志处理"""
        error_info = {
            "error_type": error.__class__.__name__,
            "statement": getattr(error, "statement", None),
            "orig": str(error.orig) if hasattr(error, "orig") else None
        }

        self.logger.error(
            "Database error occurred",
            extra={
                "error_info": error_info,
                "stack_trace": True
            }
        )