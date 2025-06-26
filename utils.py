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

