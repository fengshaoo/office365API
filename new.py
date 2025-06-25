# -*- coding: UTF-8 -*-
import itertools
import time
import logging
from datetime import datetime, timezone, timedelta

import requests
from requests import session
from sqlalchemy.sql.functions import now

from config import Config
from custom_session import CustomSession
from dao.account_service import AccountService
from dao.job_detail_service import JobDetailService
from pojo.account import Account
from pojo.job_detail import JobDetail
from utils import Utils
from errorInfo import ErrorCode
from errorInfo import BasicException
from configuration.logger_config import setup_logger


class Foo(object):
    """
    计数器，用于统计失败次数
    """
    _count = 0

    @property
    def count(self):
        return Foo._count

    @count.setter
    def count(self, num):
        Foo._count = num


class API(object):

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("日志初始化配置完成")

        self.session = CustomSession()


    def __enter__(self):
        self.logger.info("加载环境变量")
        try:
            Config.load()
        except Exception as e:
            raise BasicException(ErrorCode.INIT_ENVIRONMENT_ERROR, extra=e)

        # 生成本次任务的唯一id
        self.job_id = Utils.generate_id()
        self.logger.info(f"本次任务ID：{self.job_id}")

        # 日志文件名称写入环境变量
        self.logger.info("配置写入 GITHUB_ENV 文件")
        try:
            Utils.write_env(
                [
                    "LOG_FILENAME",
                    "JOB_ID"
                ],
                [
                    Config.LOG_FILENAME,
                    self.job_id
                ]
            )
        except Exception as e:
            raise BasicException(ErrorCode.WRITE_FILE_ERROR, extra=e)

        # 配置日志服务器连接变量
        if Config.LOG_SERVER_URL is None:
            self.logger.warning("未配置日志服务器，采用本地模式，该模式下无日志存档")
        else:
            try:
                # 解析日志服务器url
                user, rest = Config.LOG_SERVER_URL.split('@', 1)
                host, file_path = rest.split('/', 1)
                Utils.write_env(
                    [
                        "LOG_SERVER_USER",
                        "LOG_SERVER_HOST",
                        "LOG_FILE_PATH"
                    ],
                    [
                        user,
                        host,
                        file_path
                    ]
                )
            except Exception as e:
                raise BasicException(ErrorCode.WRITE_FILE_ERROR, extra=e)

        # 建立数据库连接
        if Config.DATABASE_URL is None:
            self.logger.warning("未配置数据库，采用本地模式")
        else:
            try:
                self.job_detail_service = JobDetailService()
                self.accountService = AccountService()
            except Exception as e:
                raise BasicException(ErrorCode.DATABASE_CONNECT_ERROR, extra=e)

            # 初始化本次任务的数据库
            new_job = JobDetail(
                id = self.job_id,
                start_time = datetime.now(),
                end_time = None,
                process = 'init',
                status = 'running',
                job_status = 0
            )
            self.job_detail_service.create_job(new_job)
            self.logger.info("数据库初始化完成")
        return self

    def getmstoken(self, client_id, client_secret, refresh_token, proxy, user_agent):
        """
        调用 OAuth2 刷新接口，返回 dict 中至少包含:
          - access_token
          - refresh_token (可能更新；若没有则继续使用旧的)
          - expires_in (秒)
        """
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': 'http://localhost:53682/',
            "scope": "https://graph.microsoft.com/.default"
        }

        resp = self.session.post(
            Config.ACCESS_TOKEN_URI,
            data=data,
            timeout=10,
            proxy=proxy,
            user_agent=user_agent
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_user_info(self, access_token):
        """
        用 access_token 调用用户信息接口，例如 Microsoft Graph /me
        返回 JSON dict；若失败抛异常或返回 None
        """
        headers = {'Authorization': f'Bearer {access_token}'}
        resp = self.session.get(
            "https://graph.microsoft.com/v1.0/me",
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            error_info = None
            if resp.status_code == 401:
                error_info = ErrorCode.PREMISSION_DENIED
            else:
                error_info = ErrorCode.INVOKE_API_ERROR
            raise BasicException(error_info, extra=f"Code: {resp.status_code}, Text: {resp.text}")

    def get_access_and_userinfo(self, account_key, refresh_token, proxy, user_agent):
        """
        account_key: "MS_TOKEN" 或 "MS_TOKEN_01" 等
        refresh_token: 初始 refresh_token（从 Config.USER_TOKEN_DICT 取）
        返回 (access_token, user_info_dict)
        """
        client_id = Config.CLIENT_ID
        client_secret = Config.CLIENT_SECRET

        access_token = None
        expires_at = None
        user_info = None

        rec = None
        db_url = Config.DATABASE_URL
        if db_url is not None:
            rec = self.accountService.get_by_env_name(account_key)

        # 获取token
        if db_url is None or rec is None:
            token_data = self.getmstoken(client_id, client_secret, refresh_token, proxy, user_agent)
            access_token = token_data.get("access_token")
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token_data.get("expires_in")))
        else:
            access_token = rec.access_token
            expires_at = rec.expires_at

        # 存储本次获取的信息
        if db_url is not None and rec is None:
            self.logger.info("数据库模式，插入用户token信息")
            new_account = Account(
                env_name = account_key,
                access_token = access_token,
                refresh_token = refresh_token,
                expires_at = expires_at
            )
            self.accountService.insert(new_account)

        # 判断是否有有效 access_token
        valid_access = False
        if access_token and expires_at:
            # 若在未来且剩余时间>10秒，视为有效；否则视为过期
            if expires_at > datetime.now(timezone.utc) + timedelta(seconds=10):
                # 尝试获取用户信息
                try:
                    user_info = self.fetch_user_info(access_token)
                    valid_access = True
                except BasicException as e:
                    if e.code != 2401:
                        raise e
        if not valid_access:
            self.logger.info("access_token 失效，尝试刷新")
            # 刷新
            token_data = self.getmstoken(client_id, client_secret, refresh_token, proxy, user_agent)
            access_token = token_data.get("access_token")
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token_data.get("expires_in")))

            # 更新数据库
            if db_url is not None:
                self.logger.info("数据库模式，更新用户token信息")
                self.accountService.update(
                    env_name = account_key,
                    access_token = access_token,
                    expires_at = expires_at
                )
            # 重新获取用户信息
            user_info = self.fetch_user_info(access_token)

        return access_token, user_info



    def run(self, account_key, refresh_token, proxy, user_agent, *args):
        self.logger.info("更新数据库进入任务调用")
        try:
            self.job_detail_service.update_process(self.job_id, "run_api")
            # 1.登陆
            self.logger.info("用户登陆")
            access_token, user_info = self.get_access_and_userinfo(account_key, refresh_token, proxy, user_agent)
            self.logger.info(f"已获取用户信息：access_token: ******, user_info: {user_info}")
            self.logger.info("调试终止程序")
        except Exception as e:
            raise BasicException(ErrorCode.MAIN_LOGICAL_ERROR, extra=e)



        # 2.拉取邮件和日程

        # 3.随机调用



    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def entrance():
    time_formate = "%Y-%m-%d %H:%M:%S"
    start_time = time.time()
    logging.info(f"开始执行, start time: {format(time.strftime(time_formate))}")

    try:
        with API() as api:
            scheduled_tasks = Utils.schedule_startup(Utils.select_enabled_indices(), api.run)
            # 遍历打印每个已调度账号的信息
            for account_key, delay, timer in scheduled_tasks:
                print(f"账号 {account_key} 计时器对象: {timer}")

    except Exception as e:
        logging.error(e)

    end_time = time.time()
    duration = end_time - start_time
    mins, secs = divmod(duration, 60)

    logging.info(f"执行完成, end time: {time.strftime(time_formate)}")
    logging.info(f"本次运行耗时 {int(mins)} m {secs:.2f} s")


if __name__ == "__main__":
    # 日志初始化:
    setup_logger()
    # 进入主逻辑
    entrance()
