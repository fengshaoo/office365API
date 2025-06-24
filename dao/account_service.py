from datetime import datetime

from configuration.base_db_session import BaseDBSession
from pojo.account import Account
from pojo.job_detail import JobDetail


class AccountService(BaseDBSession):
    def __init__(self, database_url: str = None):
        super().__init__(database_url)

    def get_by_env_name(self, env_name: int):
        with self.get_session() as session:
            return session.query(Account).filter(Account.env_name == env_name).first()

    def create_job(self, account: Account):
        with self.get_session() as session:
            session.add(account)

    def update_access_token(self, env_name: int, access_token: str):
        with self.get_session() as session:
            account = session.query(Account).filter(Account.env_name == env_name).first()
            if account:
                account.access_token = access_token