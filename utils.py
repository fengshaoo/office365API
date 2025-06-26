import argparse
import threading
from datetime import datetime, timezone, timedelta

import requests
import copy
import json
import time
import random
import logging
import os

from sqlalchemy import make_url, create_engine
from sqlalchemy.orm import sessionmaker

from config import Config
from dao.job_detail_service import JobDetailService
from errorInfo import ErrorCode
from errorInfo import BasicException
from configuration.logger_config import setup_logger


class Utils:
    """
    工具类
    """
    @staticmethod
    def sendmessage(i, run_times):
        """
        出现错误时发送错误消息
        :param i: 错误次数
        :param run_times: 运行时间
        :return:
        """
        a = 12 - i
        local_time = time.strftime('%Y-%m-%d %H:%M:%S')

        # 失败提醒功能
        if Config.TELEGRAM_MESSAGE_STATUS:
            if i != 12:
                telegram_text = "Office365AutoAPI调用存在异常情况！\n调用总数： 12 \n成功个数： {} \n失败个数： {} \n调用持续时长为： {}时{}分{}秒 \n调用时间： {} (UTC) ".format(
                    a, i, run_times[0], run_times[1], run_times[2], local_time)
            else:
                telegram_text = "Office365调用token失效，请及时更新token！\n调用总数： 12 \n成功个数： {} \n失败个数： {} \n调用持续时长为： {}时{}分{}秒 \n调用时间： {} (UTC) ".format(
                    a, i, run_times[0], run_times[1], run_times[2], local_time)

            telegram_address = Config.TELEGRAM_URL + Config.TELEGRAM_TOKEN + "/sendMessage?chat_id=-" + Config.TELEGRAM_CHAT_ID + "&text=" + telegram_text
            requests.get(telegram_address)
        else:
            # TODO 若telegram失效则启用邮件通知
            pass

    @staticmethod
    def getmstoken(client_id, client_secret, ms_token):
        """
        获取微软access_token
        :param client_id: 应用id
        :param client_secret: 应用密钥
        :param ms_token: 账号的 refresh_token
        :return: 获取到的 access_token
        """

        headers = copy.deepcopy(Config.REQUEST_COMMON_HEADERS)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['User-Agent'] = random.choice(Config.USER_AGENT_LIST)
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': ms_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': Config.REDIRECT_URI
        }
        html = requests.post(Config.ACCESS_TOKEN_URI, headers= headers, data= data)
        jsontxt = json.loads(html.text)

        try:
            access_token = jsontxt['access_token']
            return access_token
        except KeyError:
            print("未识别到access_token，可能ms_token已过期！")
            # 发送错误信息
            return -1

    # TODO 后续加入数据库 首先使用旧access_token 报错后再刷新
    @staticmethod
    def getaccess():
        # 一次性获取access_token，降低获取率
        for a in range(1, int(Config.APP_NUM) + 1):
            client_id = Config.CLIENT_ID
            client_secret = Config.CLIENT_SECRET
            ms_token = Config.REFRESH_TOKEN
            Config.ACCESS_TOKEN_LIST[a - 1] = Utils.getmstoken(client_id, client_secret, ms_token)
            if Config.ACCESS_TOKEN_LIST[a - 1] == -1:
                return -1

    @staticmethod
    def post_process() -> None:
        """
        连接 MySQL 数据库，完成任务的后处理操作
        """
        # 检查是否配置数据库
        database_url = os.getenv("DATABASE_URL")
        if database_url is None:
            logging.warning("未配置数据库，采用本地模式，无需执行后处理操作")
            logging.info("任务完成，正常退出")
            return
        # 检查job_id是否设置
        job_id = os.environ.get("JOB_ID")
        if job_id is None:
            raise BasicException(
                ErrorCode.FIELD_MISSING,
                extra="数据库连接模式下 job_id 未找到，请检查主函数是否设置id或是否写入GITHUB_ENV文件"
            )

        logging.info("开始执行任务后处理，状态写入数据库")
        try:
            job_id = int(job_id)
            job_detail_service = JobDetailService(database_url)
            job_detail_service.post_db_process(job_id)
        except Exception as e:
            raise BasicException(ErrorCode.UPDATE_DATABASE_ERROR, extra=e)
        logging.info(f"后置处理已完成，更新 job_id={job_id} 的任务状态为 success")

    @staticmethod
    def write_env(keys, values):
        """
        向 GitHub Actions 文件写入环境变量
        :param keys: 一个字符串或字符串列表，表示环境变量名
        :param values: 一个字符串或字符串列表，表示对应的值
        :return: None
        """
        # 如果是单个键值对，转为列表处理
        if isinstance(keys, str):
            keys = [keys]
        if isinstance(values, str):
            values = [values]

        if len(keys) != len(values):
            raise ValueError("keys 和 values 的长度不一致")
        # GitHub工作流变量文件
        github_env = os.getenv("GITHUB_ENV")

        with open(github_env, 'a') as f:
            for k, v in zip(keys, values):
                f.write(f"{k}={v}\n")


    @staticmethod
    def generate_id() -> str:
        """
        生成一个16位纯数字的 job_id：
        - 前部分为去掉前两位年份的时间戳（毫秒级）
        - 后部分为随机数字，补齐到16位
        :return: 16位字符串形式的 job_id
        """
        # 获取当前毫秒级时间戳
        timestamp_ms = int(time.time() * 1000)  # e.g. 20250623150302123
        timestamp_str = str(timestamp_ms)[2:]  # 去掉前两位年份

        # 计算随机数长度
        remaining_length = 16 - len(timestamp_str)
        random_part = ''.join(random.choices('0123456789', k=remaining_length))

        job_id = timestamp_str + random_part
        return job_id[:16]

    @staticmethod
    def to_beijing_time(dt: datetime) -> datetime:
        """
        将任意 datetime 转换为北京时间（UTC+8）。
        :param dt: 要转换的时间
        :return: 北京时间
        """
        if dt.tzinfo is None:
            # naive 时间，假定为 UTC 时间
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone(timedelta(hours=8)))

    @staticmethod
    def get_beijing_time(offset_seconds: int = 0) -> datetime:
        """
        获取当前时间指定偏移秒数的北京时间
        :param offset_seconds: 基于当前时间的偏移秒数
        :return: 北京时间
        """
        utc_now = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
        beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
        return beijing_time




    @staticmethod
    def select_enabled_indices():
        """
        根据 ENABLE_NUM 随机选择若干账号，返回索引列表。
        索引对应 USER_TOKEN_DICT keys 的顺序，顺序随机。
        例如返回 [0,2,5] 表示选中字典中第 0、2、5 个 key。
        """
        if Config.ENABLE_NUM == -1:
            # 随机打乱全部索引顺序返回
            indices = list(range(Config.APP_NUM))
        else:
            indices = random.sample(range(Config.APP_NUM), Config.ENABLE_NUM)
        random.shuffle(indices)
        return indices

    @staticmethod
    def schedule_startup(enabled_indices, startup_func, *args, **kwargs):
        """
        enabled_indices: list of indices (对应 USER_TOKEN_DICT keys 的顺序)
        startup_func: 要启动账号时调用的函数，签名如 func(account_key, refresh_token, ...)
        args, kwargs: 额外传给 startup_func 的参数

        调度所有账号在 Config.MAX_START_TIME 内启动，使用 threading.Timer。
        """
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
            logging.info(f"[Scheduler] Scheduled account {account_key} with delay {delay:.2f}s, proxy={proxy}, UA={user_agent}")

        for item in scheduled:
            timer = item[2]
            timer.join()

        return scheduled



if __name__ == "__main__":
    setup_logger()
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', choices=["PostProcess", 'task2'], required=True, help='任务名称')
    args = parser.parse_args()

    # 任务全部完成的后处理
    if args.task == "PostProcess":
        try:
            Utils.post_process()
        except Exception as e:
            logging.error(e)

