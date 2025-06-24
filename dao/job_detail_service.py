from configuration.base_db_session import BaseDBSession
from pojo.job_detail import JobDetail


class JobDetailService(BaseDBSession):
    def __init__(self):
        super().__init__()

    def get_by_id(self, job_id: int):
        with self.get_session() as session:
            return session.query(JobDetail).filter(JobDetail.id == job_id).first()

    def create_job(self, job: JobDetail):
        with self.get_session() as session:
            session.add(job)

    def update_status(self, job_id: int, status: str):
        with self.get_session() as session:
            job = session.query(JobDetail).filter(JobDetail.id == job_id).first()
            if job:
                job.status = status

    def delete_job(self, job_id: int):
        with self.get_session() as session:
            job = session.query(JobDetail).filter(JobDetail.id == job_id).first()
            if job:
                session.delete(job)