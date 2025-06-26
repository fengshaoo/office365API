# -*- coding: UTF-8 -*-
import sys
import time
import logging
import random
import threading
import requests
from datetime import datetime, timezone, timedelta

from config import Config
from configuration.custom_session import CustomSession
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


class RunService(object):

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


    # def getmstoken(self, client_id, client_secret, refresh_token, proxy, user_agent):
    #     """
    #     调用 OAuth2 刷新接口，返回 dict 中至少包含:
    #       - access_token
    #       - refresh_token (可能更新；若没有则继续使用旧的)
    #       - expires_in (秒)
    #     """
    #     data = {
    #         'grant_type': 'refresh_token',
    #         'refresh_token': refresh_token,
    #         'client_id': client_id,
    #         'client_secret': client_secret,
    #         'redirect_uri': Config.REDIRECT_URI,
    #         "scope": "https://graph.microsoft.com/.default"
    #     }
    #
    #     resp = self.session.post(
    #         Config.ACCESS_TOKEN_URI,
    #         data=data,
    #         timeout=10,
    #         proxy=proxy,
    #         headers = {
    #             "User-Agent": user_agent,
    #             "Content-Type": "application/x-www-form-urlencoded",
    #         }
    #     )
    #     resp.raise_for_status()
    #     return resp.json()
    #
    # def fetch_user_info(self, access_token, user_agent):
    #     """
    #     用 access_token 调用用户信息接口，例如 Microsoft Graph /me
    #     返回 JSON dict；若失败抛异常或返回 None
    #     """
    #     headers = {'Authorization': f'Bearer {access_token}'}
    #     resp = self.session.get(
    #         "https://graph.microsoft.com/v1.0/me",
    #         headers = {
    #             "Authorization": f"Bearer {access_token}",
    #             "User-Agent": user_agent,
    #         },
    #         timeout=10
    #     )
    #     resp.raise_for_status()
    #     return resp.json()
    #
    # def get_access_and_userinfo(self, account_key, refresh_token, proxy, user_agent):
    #     """
    #     account_key: "MS_TOKEN" 或 "MS_TOKEN_01" 等
    #     refresh_token: 初始 refresh_token（从 Config.USER_TOKEN_DICT 取）
    #     返回 (access_token, user_info_dict)
    #     """
    #     client_id = Config.CLIENT_ID
    #     client_secret = Config.CLIENT_SECRET
    #
    #     access_token = None
    #     expires_at = None
    #     user_info = None
    #
    #     db_rec = None
    #     db_url = Config.DATABASE_URL
    #     if db_url is not None:
    #         db_rec = self.accountService.get_by_env_name(account_key)
    #
    #     # 获取token
    #     if db_url is None or db_rec is None:
    #         token_data = self.getmstoken(client_id, client_secret, refresh_token, proxy, user_agent)
    #         access_token = token_data.get("access_token")
    #         expires_at = Utils.get_beijing_time(int(token_data.get("expires_in")))
    #     else:
    #         access_token = db_rec.access_token
    #         expires_at = Utils.to_beijing_time(db_rec.expires_at)
    #
    #     # 存储本次获取的信息
    #     if db_url is not None and db_rec is None:
    #         self.logger.info("数据库模式，插入用户token信息")
    #         new_account = Account(
    #             env_name = account_key,
    #             access_token = access_token,
    #             refresh_token = refresh_token,
    #             expires_at = expires_at
    #         )
    #         self.accountService.insert(new_account)
    #
    #     # 判断是否有有效 access_token
    #     valid_access = False
    #     if access_token and expires_at:
    #         # 若在未来且剩余时间>10秒，视为有效；否则视为过期
    #         if expires_at > Utils.get_beijing_time(10):
    #             # 尝试获取用户信息
    #             try:
    #                 user_info = self.fetch_user_info(access_token, user_agent)
    #                 valid_access = True
    #             except requests.exceptions.HTTPError as e:
    #                 response = e.response
    #                 if response is None or response.status_code != 401:
    #                     raise BasicException(ErrorCode.INVOKE_API_ERROR, extra=e)
    #     if not valid_access:
    #         self.logger.info("access_token 失效，尝试刷新")
    #         # 刷新
    #         token_data = self.getmstoken(client_id, client_secret, refresh_token, proxy, user_agent)
    #         access_token = token_data.get("access_token")
    #         expires_at = Utils.get_beijing_time(int(token_data.get("expires_in")))
    #         self.logger.info("刷新成功")
    #
    #         # 更新数据库
    #         if db_url is not None:
    #             self.logger.info("数据库模式，更新用户token信息")
    #             self.accountService.update(
    #                 env_name = account_key,
    #                 access_token = access_token,
    #                 expires_at = expires_at
    #             )
    #         # 重新获取用户信息
    #         try:
    #             user_info = self.fetch_user_info(access_token, user_agent)
    #         except Exception as e:
    #             raise BasicException(ErrorCode.INVOKE_API_ERROR, extra=e)
    #
    #     return access_token, user_info
    #
    #
    #
    # def run(self, account_key, refresh_token, proxy, user_agent, *args):
    #     self.logger.info("更新数据库进入任务调用")
    #     try:
    #         self.job_detail_service.update_process(self.job_id, "run_api")
    #         # 1.登陆
    #         self.logger.info("用户登陆")
    #         access_token, user_info = self.get_access_and_userinfo(account_key, refresh_token, proxy, user_agent)
    #         # self.logger.info(f"已获取用户信息：access_token: ******, user_info: {user_info}")
    #
    #
    #         if Config.ENV_MODE == "DEBUG":
    #             self.logger.info("调试终止程序")
    #             sys.exit()
    #     except Exception as e:
    #         raise BasicException(ErrorCode.MAIN_LOGICAL_ERROR, extra=e)
    #
    #
    #
    #     # 2.拉取邮件和日程
    #
    #     # 3.随机调用


    def schedule_startup(self, enabled_indices, startup_func, *args, **kwargs):
        """
        enabled_indices: list of indices (对应 USER_TOKEN_DICT keys 的顺序)
        startup_func: 要启动账号时调用的函数，签名如 func(account_key, refresh_token, ...)
        args, kwargs: 额外传给 startup_func 的参数

        调度所有账号在 Config.MAX_START_TIME 内启动，使用 threading.Timer。
        """
        self.logger.info("更新数据库进入任务调用")
        try:
            self.job_detail_service.update_process(self.job_id, "run_api")
        except Exception as e:
            raise BasicException(ErrorCode.UPDATE_DATABASE_ERROR, extra=e)

        total = len(enabled_indices)
        if total == 0:
            return []

        interval = Config.MAX_START_DELAY / total
        # keys 顺序
        keys = list(Config.USER_TOKEN_DICT.keys())
        scheduled = []  # 存放 (account_key, delay, timer_obj)

        for idx_pos, idx in enumerate(enabled_indices):
            # idx_pos in [0, total-1], idx 是 USER_TOKEN_DICT 的索引
            start = idx_pos * interval
            end = (idx_pos + 1) * interval
            delay = random.uniform(start, end)
            account_key = keys[idx]
            refresh_token = Config.USER_TOKEN_DICT[account_key]

            # 随机选择 proxy 和 UA
            proxy = random.choice(Config.PROXIES) if Config.PROXIES else None
            user_agent = random.choice(Config.USER_AGENT_LIST) if Config.USER_AGENT_LIST else None

            # 定义调用：用 lambda 捕获当前变量
            timer = threading.Timer(
                delay,
                startup_func,
                args=(account_key, refresh_token, proxy, user_agent, *args),
                kwargs=kwargs
            )
            timer.daemon = False  # 主线程等待
            timer.start()
            scheduled.append((account_key, delay, timer))
            logging.info(
                f"[Scheduler] Scheduled account {account_key} with delay {delay:.2f}s, proxy={proxy}, UA={user_agent}")

        for item in scheduled:
            timer = item[2]
            timer.join()

        return scheduled



    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("执行主进程清理工作")





class CallAPI(object):

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.session = CustomSession()

        # 建立数据库连接
        if Config.DATABASE_URL is not None:
            try:
                self.accountService = AccountService()
            except Exception as e:
                raise BasicException(ErrorCode.DATABASE_CONNECT_ERROR, extra=e)


    def get_ms_token(self, client_id, client_secret, refresh_token, proxy, user_agent):
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
            'redirect_uri': Config.REDIRECT_URI,
            "scope": "https://graph.microsoft.com/.default"
        }

        resp = self.session.post(
            Config.ACCESS_TOKEN_URI,
            data=data,
            timeout=10,
            proxy=proxy,
            headers = {
                "User-Agent": user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_user_info(self, access_token, user_agent):
        """
        用 access_token 调用用户信息接口，例如 Microsoft Graph /me
        返回 JSON dict；若失败抛异常或返回 None
        """
        headers = {'Authorization': f'Bearer {access_token}'}
        resp = self.session.get(
            "https://graph.microsoft.com/v1.0/me",
            headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": user_agent,
            },
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()

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

        db_rec = None
        db_url = Config.DATABASE_URL
        if db_url is not None:
            db_rec = self.accountService.get_by_env_name(account_key)

        # 获取token
        if db_url is None or db_rec is None:
            token_data = self.get_ms_token(client_id, client_secret, refresh_token, proxy, user_agent)
            access_token = token_data.get("access_token")
            expires_at = Utils.get_beijing_time(int(token_data.get("expires_in")))
        else:
            access_token = db_rec.access_token
            expires_at = Utils.to_beijing_time(db_rec.expires_at)

        # 存储本次获取的信息
        if db_url is not None and db_rec is None:
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
            if expires_at > Utils.get_beijing_time(10):
                # 尝试获取用户信息
                try:
                    user_info = self.fetch_user_info(access_token, user_agent)
                    valid_access = True
                except requests.exceptions.HTTPError as e:
                    response = e.response
                    if response is None or response.status_code != 401:
                        raise BasicException(ErrorCode.INVOKE_API_ERROR, extra=e)
        if not valid_access:
            self.logger.info("access_token 失效，尝试刷新")
            # 刷新
            token_data = self.get_ms_token(client_id, client_secret, refresh_token, proxy, user_agent)
            access_token = token_data.get("access_token")
            expires_at = Utils.get_beijing_time(int(token_data.get("expires_in")))
            self.logger.info("刷新成功")

            # 更新数据库
            if db_url is not None:
                self.logger.info("数据库模式，更新用户token信息")
                self.accountService.update(
                    env_name = account_key,
                    access_token = access_token,
                    expires_at = expires_at
                )
            # 重新获取用户信息
            try:
                user_info = self.fetch_user_info(access_token, user_agent)
            except Exception as e:
                raise BasicException(ErrorCode.INVOKE_API_ERROR, extra=e)

        return access_token, user_info



    def run(self, account_key, refresh_token, proxy, user_agent, *args):
        try:
            # 1.登陆
            self.logger.info("用户登陆")
            access_token, user_info = self.get_access_and_userinfo(account_key, refresh_token, proxy, user_agent)
            # self.logger.info(f"已获取用户信息：access_token: ******, user_info: {user_info}")


            if Config.ENV_MODE == "DEBUG":
                self.logger.info("调试终止程序")
                sys.exit()
        except Exception as e:
            raise BasicException(ErrorCode.MAIN_LOGICAL_ERROR, extra=e)



        # 2.拉取邮件和日程

        # 3.随机调用


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("执行主进程清理工作")

def entrance():
    time_formate = "%Y-%m-%d %H:%M:%S"
    start_time = time.time()
    logging.info(f"开始执行, start time: {format(time.strftime(time_formate))}")

    try:
        with RunService() as run_service:
            call_api = CallAPI()
            scheduled_tasks = run_service.schedule_startup(Utils.select_enabled_indices(), call_api.run)
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
