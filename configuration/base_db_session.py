import logging

from sqlalchemy import create_engine, text, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url
from contextlib import contextmanager

from config import Config
from errorInfo import BasicException, ErrorCode

SENSITIVE_KEYS = {"access_token", "refresh_token", "password", "secret", "api_key", "token"}
SENSITIVE_PATTERNS = {"password", "secret", "token"}  # 字段名包含这些关键词也视为敏感

class SensitiveDataFilter:
    @staticmethod
    def sanitize_value(key: str, value: any) -> any:
        """检查并脱敏单个值"""
        key_lower = key.lower()
        if (key in SENSITIVE_KEYS or
            any(pattern in key_lower for pattern in SENSITIVE_PATTERNS)):
            return "<sensitive>"
        return value

    @staticmethod
    def sanitize_params(params: dict) -> dict:
        """脱敏整个参数字典"""
        if not isinstance(params, dict):
            return {}
        return {k: SensitiveDataFilter.sanitize_value(k, v) for k, v in params.items()}

    @staticmethod
    def sanitize_statement(statement: str) -> str:
        """脱敏SQL语句中的敏感值（简单实现）"""
        # 实际项目中可用正则表达式更精确处理
        for pattern in SENSITIVE_PATTERNS:
            if pattern in statement.lower():
                return "<sql_with_sensitive_data>"
        return statement

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
                # echo=True,
                hide_parameters=True
            )
            BaseDBSession._SessionFactory = sessionmaker(bind=BaseDBSession._engine)

            # 注册全局SQL事件监听器（脱敏处理）
            # @event.listens_for(BaseDBSession._engine, "before_cursor_execute")
            # def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            #     context._sensitive_statement = SensitiveDataFilter.sanitize_statement(statement)
            #     if parameters:
            #         context._sensitive_params = SensitiveDataFilter.sanitize_params(
            #             parameters if isinstance(parameters, dict) else {}
            #         )
            #
            # BaseDBSession._SessionFactory = sessionmaker(
            #     bind=BaseDBSession._engine,
            #     autoflush=False,
            #     expire_on_commit=False
            # )

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

            # self._log_sql_error(e)
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
            # 设置只读模式（MySQL语法）
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

        # 获取脱敏后的参数
        params = {}
        if hasattr(error, "params"):
            params = SensitiveDataFilter.sanitize_params(error.params)

        logging.error(
            "Database error occurred",
            extra={
                "error_info": error_info,
                "sensitive_params": params,
                "stack_trace": True
            }
        )