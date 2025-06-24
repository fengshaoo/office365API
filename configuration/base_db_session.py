from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url
from contextlib import contextmanager

from config import Config

class BaseDBSession:
    _engine = None
    _SessionFactory = None

    def __init__(self, database_url: str = None):
        if not BaseDBSession._engine:
            self.database_url = database_url or Config.DATABASE_URL
            db_url = make_url(f"mysql+pymysql://{Config.DATABASE_URL}")
            BaseDBSession._engine = create_engine(db_url, pool_pre_ping=True)
            BaseDBSession._SessionFactory = sessionmaker(bind=BaseDBSession._engine)

    @contextmanager
    def get_session(self):
        session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()