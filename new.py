# -*- coding: UTF-8 -*-
import time
import logging
from datetime import datetime

import requests

from config import Config
from dao.account_service import AccountService
from dao.job_detail_service import JobDetailService
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


    def __enter__(self):
        self.logger.info("加载环境变量")
        try:
            Config.load()
        except Exception as e:
            raise BasicException(ErrorCode.INIT_ENVIRONMENT_ERROR, extra=e)

        # 生成本次任务的唯一id
        job_id = Utils.generate_id()
        self.logger.info(f"本次任务ID：{job_id}")

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
                    job_id
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
            except Exception as e:
                raise BasicException(ErrorCode.DATABASE_CONNECT_ERROR, extra=e)

            # 初始化本次任务的数据库
            new_job = JobDetail(
                id = job_id,
                start_time = datetime.now(),
                end_time = None,
                process = 'init',
                status = 'running',
                job_status = 0
            )
            self.job_detail_service.create_job(new_job)
            self.logger.info("数据库初始化完成")
        return self

    def getmstoken(self, client_id, client_secret, refresh_token):
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
            'redirect_uri': 'http://localhost:53682/'
        }
        resp = requests.post(
            'https://login.microsoftonline.com/common/oauth2/v2.0/token',
            data=data
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_user_info(access_token):
        """
        用 access_token 调用用户信息接口，例如 Microsoft Graph /me
        返回 JSON dict；若失败抛异常或返回 None
        """
        headers = {'Authorization': f'Bearer {access_token}'}
        resp = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        if resp.status_code == 200:
            return resp.json()
        else:
            # 根据实际需求，可打印日志或抛异常
            # 如果是 401，可能 token 失效
            return None

    def get_access_and_userinfo(self, account_key, refresh_token):
        """
        account_key: "MS_TOKEN" 或 "MS_TOKEN_01" 等
        refresh_token: 初始 refresh_token（从 Config.USER_TOKEN_DICT 取）
        返回 (access_token, user_info_dict)
        """
        db_url = getattr(Config, 'DATABASE_URL', None)
        client_id = Config.CLIENT_ID
        client_secret = Config.CLIENT_SECRET

        # 如果无数据库配置，直接刷新
        if not db_url:
            token_data = self.getmstoken(client_id, client_secret, refresh_token)
            access_token = token_data['access_token']
            # 可更新 Config.USER_TOKEN_DICT 中的 refresh_token
            new_refresh = token_data.get('refresh_token', refresh_token)
            Config.USER_TOKEN_DICT[account_key] = new_refresh
            # 获取用户信息
            user_info = self.fetch_user_info(access_token)
            return access_token, user_info

        # 1. 查询记录
        self.accountService = AccountService()
        rec = self.accountService.get_by_env_name(account_key)

        now = datetime.now(timezone.utc)

        if rec is None:
            # 无记录，则插入一条，仅含 refresh_token
            ins = insert(account_table).values(
                env_name=account_key,
                access_token=None,
                refresh_token=refresh_token,
                expires_at=None
            )
            session.execute(ins)
            session.commit()
            rec = session.execute(stmt).first()

        row = rec._mapping
        stored_access = row.get('access_token')
        stored_refresh = row.get('refresh_token') or refresh_token
        expires_at = row.get('expires_at')  # 可能为 None

        # 判断是否有有效 access_token
        valid_access = False
        if stored_access and expires_at:
            # 若在未来且剩余时间>60秒，视为有效；否则视为过期
            if expires_at > now + timedelta(seconds=60):
                # 试用 stored_access 获取用户信息
                user_info = fetch_user_info(stored_access)
                if user_info:
                    valid_access = True
                    access_token = stored_access
                    # refresh_token 可能同步更新 Config.USER_TOKEN_DICT
                # else: 视为无效，需要刷新
        if not valid_access:
            # 刷新
            token_data = getmstoken(client_id, client_secret, stored_refresh)
            access_token = token_data['access_token']
            new_refresh = token_data.get('refresh_token', stored_refresh)
            expires_in = token_data.get('expires_in', 3600)
            new_expires_at = now + timedelta(seconds=int(expires_in))
            # 更新数据库
            upd = update(account_table).where(account_table.c.env_name == account_key).values(
                access_token=access_token,
                refresh_token=new_refresh,
                expires_at=new_expires_at
            )
            session.execute(upd)
            session.commit()
            # 更新本地 Config.USER_TOKEN_DICT
            Config.USER_TOKEN_DICT[account_key] = new_refresh
            # 获取用户信息
            user_info = fetch_user_info(access_token)

        session.close()
        return access_token, user_info



    def run(self):
        self.logger.info("--->成功执行到调用步骤<---")
        self.job_detail_service.update_process("run_api")

        # 1.登陆

        # 2.拉取邮件和日程

        # 3.随机调用



    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def entrance():
    try:
        with API() as api:
            api.logger.info("调用开始执行")
            api.run()
            local_time = time.strftime('%Y-%m-%d %H:%M:%S')
            api.logger.info("执行完成，完成时间{}".format(local_time))
    except Exception as e:
        logging.error(e)


if __name__ == "__main__":
    setup_logger()  # 日志初始化
    entrance()
