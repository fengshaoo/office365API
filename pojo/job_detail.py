from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, SmallInteger, BigInteger

Base = declarative_base()

class JobDetail(Base):
    __tablename__ = 'job_detail'

    id = Column(BigInteger, primary_key=True, autoincrement=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    process = Column(String(255))
    status = Column(String(50))
    job_status = Column(SmallInteger)
    ip_address = Column(String(45))