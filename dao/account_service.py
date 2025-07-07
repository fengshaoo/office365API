
from configuration.base_db_session import BaseDBSession
from pojo.account import Account


class AccountService(BaseDBSession):
    def __init__(self, database_url: str = None):
        super().__init__(database_url)

    def get_by_env_name(self, env_name: str):
        with self.get_session() as session:
            result = session.query(Account).filter(Account.env_name == env_name).first()
            if result:
                # 手动构造一个脱离 session 的 Account 对象
                account = Account()
                for column in Account.__table__.columns:
                    setattr(account, column.name, getattr(result, column.name))
                return account
            return None

    def get_by_access_token(self, access_token: str):
        with self.get_session() as session:
            result = session.query(Account).filter(Account.access_token == access_token).first()
            if result:
                # 手动构造一个脱离 session 的 Account 对象
                account = Account()
                for column in Account.__table__.columns:
                    setattr(account, column.name, getattr(result, column.name))
                return account
            return None

    def insert(self, account: Account):
        with self.get_session() as session:
            session.add(account)

    def update_access_token(self, env_name: int, access_token: str):
        with self.get_session() as session:
            account = session.query(Account).filter(Account.env_name == env_name).first()
            if account:
                account.access_token = access_token

    def update(self, env_name: str, **fields):
        with self.get_session() as session:
            account = session.query(Account).filter(Account.env_name == env_name).first()
            if not account:
                return False

            for field, value in fields.items():
                if hasattr(account, field):
                    setattr(account, field, value)
            return True