from datetime import datetime

from configuration.base_db_session import BaseDBSession
from pojo.job_detail import JobDetail


class JobDetailService(BaseDBSession):
    def __init__(self, database_url: str = None):
        super().__init__(database_url)

    def get_by_id(self, job_id: int):
        with self.get_session() as session:
            result = session.query(JobDetail).filter(JobDetail.id == job_id).first()
            if result:
                # 手动构造一个脱离 session 的 Account 对象
                job_detail = JobDetail()
                for column in JobDetail.__table__.columns:
                    setattr(job_detail, column.name, getattr(result, column.name))
                return job_detail
            return None

    def create_job(self, job: JobDetail):
        with self.get_session() as session:
            session.add(job)

    def update_process(self, job_id: str, process: str):
        with self.get_session() as session:
            job = session.query(JobDetail).filter(JobDetail.id == job_id).first()
            if job:
                job.process = process

    def delete_job(self, job_id: int):
        with self.get_session() as session:
            job = session.query(JobDetail).filter(JobDetail.id == job_id).first()
            if job:
                session.delete(job)

    def post_db_process(self, job_id: int):
        with self.get_session() as session:
            job = session.query(JobDetail).filter(JobDetail.id == job_id).first()
            if job:
                job.job_status = 1
                job.end_time = datetime.now()
                job.process = "post_process"
                job.status = "end"