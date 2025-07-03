# -*- coding: UTF-8 -*-
import sys
import time
import logging
import random
import threading
from concurrent.futures import wait

import requests
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pyexpat import features

from config import Config
from configuration.base_db_session import BaseDBSession
from configuration.custom_session import CustomSession
from configuration.thread_pool_config import ThreadPoolManager
from dao.account_service import AccountService
from dao.job_detail_service import JobDetailService
from pojo.account import Account
from pojo.account_context import AccountContext
from pojo.api_error_set import APIErrorSet
from pojo.job_detail import JobDetail
from utils import Utils
from errorInfo import ErrorCode
from errorInfo import BasicException
from configuration.logger_config import CLogger


# 线程独享变量存储
thread_local = threading.local()

class RunService(object):

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = CustomSession()


    def __enter__(self):
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


    def schedule_startup(self, enabled_indices, startup_func, *args, **kwargs):
        """
        enabled_indices: list of indices (对应 USER_TOKEN_DICT keys 的顺序)
        startup_func: 要启动账号时调用的函数，签名如 func(account_key, refresh_token, ...)
        args, kwargs: 额外传给 startup_func 的参数

        调度所有账号在 Config.MAX_START_TIME 内启动，使用 threading.Timer。
        """
        self.logger.info("进入任务调用")
        try:
            self.job_detail_service.update_process(self.job_id, "enter_RunService")
        except Exception as e:
            raise BasicException(ErrorCode.UPDATE_DATABASE_ERROR, extra=e)

        total = len(enabled_indices)
        if total == 0:
            return []

        interval = Config.MAX_START_DELAY / total
        # keys 顺序
        keys = list(Config.USER_TOKEN_DICT.keys())

        thread_pool = ThreadPoolManager.get_instance(max_workers=10, thread_name_prefix="startup")
        futures = []

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

            def delayed_start():
                try:
                    account_context = AccountContext(
                        account_key = account_key,
                        refresh_token = refresh_token,
                        proxy = proxy,
                        user_agent = user_agent
                    )

                    logging.info(
                        f"[Future] Future account {account_key} with delay {delay:.2f}s, proxy={proxy}, UA={user_agent}"
                    )
                    time.sleep(delay)
                    startup_func(account_context, *args, **kwargs)
                except Exception as e:
                    self.logger.exception(f"[Startup] 启动账号 {account_key} 异常: {e}")

            # 将延迟启动任务提交到线程池
            future = thread_pool.submit(delayed_start)
            futures.append(future)

        # 添加数据保活定时任务
        # scheduler = BackgroundScheduler(daemon=True)  # 保活任务为守护线程，主线程退出时自动停止
        # scheduler.add_job(BaseDBSession.keep_alive, IntervalTrigger(seconds=300), name="db_keep_alive")
        # scheduler.start()

        wait(futures)

        # for item in scheduled:
        #     timer = item[2]
        #     timer.join()

        self.logger.info("退出任务调用")
        try:
            self.logger.info("尝试更新数据库信息")
            self.job_detail_service.update_process(self.job_id, "exit_RunService")
        except Exception as e:
            raise BasicException(ErrorCode.UPDATE_DATABASE_ERROR, extra=e)

        return futures



    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("执行主进程清理工作")





class CallAPI(object):

    def __init__(self, session, job_detail_service, account_service):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.job_detail_service = job_detail_service
        self.account_service = account_service


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

    def get_access_and_userinfo(self, account_context: AccountContext):
        """
        account_key: "MS_TOKEN" 或 "MS_TOKEN_01" 等
        refresh_token: 初始 refresh_token（从 Config.USER_TOKEN_DICT 取）
        返回 (access_token, user_info_dict)
        """
        client_id = Config.CLIENT_ID
        client_secret = Config.CLIENT_SECRET

        account_key = account_context.account_key
        refresh_token = account_context.refresh_token
        proxy = account_context.proxy
        user_agent = account_context.user_agent

        access_token = None
        expires_at = None
        user_info = None

        db_rec = None
        db_url = Config.DATABASE_URL
        if db_url is not None:
            db_rec = self.account_service.get_by_env_name(account_key)

        # 获取token
        if db_url is None or db_rec is None:
            token_data = self.get_ms_token(client_id, client_secret, refresh_token, proxy, user_agent)
            access_token = token_data.get("access_token")
            expires_at = Utils.get_beijing_time(int(token_data.get("expires_in")))
        else:
            access_token = db_rec.access_token
            expires_at = Utils.add_beijing_timezone(db_rec.expires_at)

        # 存储本次获取的信息
        if db_url is not None and db_rec is None:
            self.logger.info("数据库模式，插入用户token信息")
            new_account = Account(
                env_name = account_key,
                access_token = access_token,
                refresh_token = refresh_token,
                expires_at = expires_at,
                create_time = Utils.get_beijing_time()
            )
            self.account_service.insert(new_account)

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
                self.account_service.update(
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

    def check_token_deadline(self, account_context: AccountContext) -> bool:
        # 判断是否存在数据库
        if Config.DATABASE_URL is None:
            self.logger.info("未配置数据库模式下刷新token")
            token_data = self.get_ms_token(
                Config.CLIENT_ID,
                Config.CLIENT_SECRET,
                account_context.refresh_token,
                account_context.proxy,
                account_context.user_agent
            )
            account_context.account_token = token_data.get("access_token")
            return True
        else:
            self.logger.info("数据库模式下刷新token")
            db_rec = self.account_service.get_by_access_token(account_context.account_token)
            if db_rec is None or Utils.add_beijing_timezone(db_rec.expires_at) > Utils.get_beijing_time():
                self.logger.info("数据库中token未过期！")
                return False
            else:
                token_data = self.get_ms_token(
                    Config.CLIENT_ID,
                    Config.CLIENT_SECRET,
                    account_context.refresh_token,
                    account_context.proxy,
                    account_context.user_agent
                )
                account_token = token_data.get("access_token")
                account_context.account_token = account_token
                self.account_service.update_access_token(account_context.account_key, account_token)
                return True

    def run_api(self, api_list, account_context: AccountContext, err_set):
        for a in range(len(api_list)):
            if Config.ENABLE_API_DELAY:
                time.sleep(random.randint(Config.API_DELAY_MIN, Config.API_DELAY_MAX))
            try:
                resp = self.session.get(
                    Config.API_LIST[api_list[a]],
                    headers={
                        "Authorization": account_context.account_token,
                        "User-Agent": account_context.user_agent,
                    },
                    proxy=account_context.proxy,
                    timeout=10
                )
                if resp.status_code == 200:
                    self.logger.info('第' + str(api_list[a]) + "号api调用成功")
                else:
                    self.logger.info(f"第 {str(api_list[a])} 号api调用失败, Detail: {resp.json}")
                    if resp.status_code == 401:
                        if self.check_token_deadline(account_context):
                            self.logger.info("token过期导致失败，已刷新")
                        else:
                            raise ValueError("token刷新过程出错，function 'check_token_deadline' return false")
                    else:
                        self.logger.error(f"API调用失败，且状态码超出预期，response:{resp.json}")
                        err_set.add(api_list[a])
            except Exception as e:
                self.logger.error(f"核心逻辑错误：API 调用失败 - {Config.API_LIST[api_list[a]]}, Detail: [{e}]")


    def core(self, account_context: AccountContext):
        begin_time = time.time()  # 统计时间开始

        # 错误集合
        err_set = APIErrorSet()

        self.logger.info('共' + str(Config.ROUNDS_PER_RUN) + '轮')
        for c in range(1, Config.ROUNDS_PER_RUN + 1):
            # 运行轮次循环
            if Config.ENABLE_RANDOM_START_DELAY:
                time.sleep(random.randint(
                    Config.ROUNDS_PER_DELAY_MIN, Config.ROUNDS_PER_DELAY_MAX))
            for a in range(1, int(Config.APP_NUM) + 1):
                self.logger.info('应用/账号 ' + str(a) + ' 的第' + str(c) + '轮' +
                      time.asctime(time.localtime(time.time())) + '\n')
                if Config.ENABLE_RANDOM_API_ORDER:
                    self.logger.info("已开启随机顺序,共12个api")
                    api_list = Utils.fix_list()
                    self.run_api(api_list, account_context, err_set)
                else:
                    self.logger.info("原版顺序,共10个api")
                    api_list = [5, 9, 8, 1, 20, 24, 23, 6, 21, 22]
                    self.run_api(api_list, account_context, err_set)
            self.logger.info("本轮结束，等待启动下一轮")


        end_time = time.time()  # 统计时间结束
        run_time = round(end_time - begin_time)
        hour = run_time // 3600
        minute = (run_time - 3600 * hour) // 60
        second = run_time - 3600 * hour - 60 * minute

        run_times = [hour, minute, second]

        if err_set.has_error:
            Utils.send_message(1, run_times, err_set, self.session)




    def run(self, account_context: AccountContext, *args):
        try:
            # 1.登陆
            self.logger.info("用户登陆")
            access_token, user_info = self.get_access_and_userinfo(account_context)
            self.logger.info(f"已获取用户信息：access_token: ******, user_info: ******")
            # 存入thread local
            thread_local.access_token = access_token
            thread_local.user_info = user_info

            # if Config.ENV_MODE == "DEBUG":
            #     self.logger.info("调试终止程序")
            #     sys.exit()

            account_context.account_token = access_token

            self.core(account_context)
            self.logger.info("核心正常结束")
        except Exception as e:
            Utils.send_message(-1, None, None, None)
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
            call_api = CallAPI(
                session=run_service.session,
                job_detail_service=run_service.job_detail_service,
                account_service=run_service.accountService
            )
            futures = run_service.schedule_startup(Utils.select_enabled_indices(), call_api.run)

    except Exception as e:
        logging.error(e)

    end_time = time.time()
    duration = end_time - start_time
    mins, secs = divmod(duration, 60)

    logging.info(f"执行完成, end time: {time.strftime(time_formate)}")
    logging.info(f"本次运行耗时 {int(mins)} m {secs:.2f} s")
    sys.exit(0)  # 强制程序退出


if __name__ == "__main__":
    # 日志初始化:
    CLogger.setup_logger()
    Config.load()
    # 进入主逻辑
    entrance()
