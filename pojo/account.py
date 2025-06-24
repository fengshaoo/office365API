from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String

Base = declarative_base()

class Account(Base):
    __tablename__ = 'account'

    env_name = Column(String(10), primary_key=True, autoincrement=False)
    access_token = Column(String(300), nullable=True)
    refresh_token = Column(String(300), nullable=True)