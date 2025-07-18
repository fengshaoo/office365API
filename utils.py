import argparse
import threading
import traceback
from datetime import datetime, timezone, timedelta
from typing import re, Union

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
from configuration.logger_config import CLogger
from pojo.api_error_set import APIErrorSet
from print_debug_info import PrintDebugInfo


class Utils:
    """
    工具类
    """
    @staticmethod
    def fix_list():
        # 随机api序列
        fixed_api = [0, 1, 5, 6, 20, 21]
        # 保证抽取到outlook,onedrive的api
        ex_api = [2, 3, 4, 7, 8, 9, 10, 22, 23, 24, 25,
                  26, 27, 13, 14, 15, 16, 17, 18, 19, 11, 12]
        # 额外抽取填充的api
        fixed_api.extend(random.sample(ex_api, 6))
        random.shuffle(fixed_api)

        # 临时添加调试功能
        if Config.ENV_MODE != "PROD":
            fixed_api = [5]

        return fixed_api

    @staticmethod
    def send_message(err_type: int, run_times = None, content: Union[str, APIErrorSet, Exception] = None):
        """
        出现失败情况时发送通知信息
        :param err_type:
        :param run_times:
        :param content:
        :return:
        """
        logging.info(f"推送消息, err_type = {err_type}")
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        telegram_url = f"{Config.TELEGRAM_URL}{telegram_token}/sendMessage"

        local_time = time.strftime('%Y-%m-%d %H:%M:%S')
        hours, minutes, seconds = 0, 0, 0
        if run_times:
            hours, minutes, seconds = run_times

        response = None
        match err_type:
            case 1:
                # 调用API存在失败情况
                if not isinstance(content, APIErrorSet):
                    raise BasicException(ErrorCode.SEND_NOTICE_ERROR, extra="传入数据类型不符")

                err_url_text = "\n".join(content.get_err_urls())

                with open("resource/tg_message_template.html") as f:
                    html_template = f.read()
                html_message = html_template.format(
                    total_calls=12,
                    fail_count=content.count,
                    hours=hours,
                    minutes=minutes,
                    seconds=seconds,
                    local_time=local_time,
                    error_list_html=err_url_text
                )
                payload = {
                    "chat_id": f"{telegram_chat_id}",
                    "text": html_message,
                    "parse_mode": "HTML"
                }

                response = requests.post(telegram_url, json=payload)

            case -1:
                # reflesh_token 失效
                title = "* Token失效提醒，请及时更新Token！*"
                telegram_address = telegram_url + "?chat_id=" + Config.TELEGRAM_CHAT_ID + "&text=" + title
                response = requests.get(telegram_address)

            case _:
                logging.info("默认错误处理")
                try:
                # 默认错误处理
                    if isinstance(content, Exception):
                        exc_type = type(content).__name__
                        exc_msg = str(content)
                    else:
                        exc_type = r"/"
                        exc_msg = str(content)

                    with open("resource/tg_message_error_template.html") as f:
                        html_template = f.read()
                    html_message = html_template.format(
                        local_time=local_time,
                        exc_type=exc_type,
                        exc_msg=exc_msg,
                    )
                    payload = {
                        "chat_id": f"{telegram_chat_id}",
                        "text": html_message,
                        "parse_mode": "HTML"
                    }

                    logging.info(f"payload:{payload}")
                    response = requests.post(telegram_url, json=payload)
                    print_debug_info = PrintDebugInfo()
                    print_debug_info.print_request_debug(response)
                except Exception as e:
                    logging.error(f"默认消息推送失败：{e}")
                finally:
                    return

        logging.info("消息推送成功")
        response.raise_for_status()


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
        mask_file = "/tmp/github_mask.sh"
        # 追加写，防止多次调用被覆盖
        with open(github_env, 'a', encoding='utf-8') as env_file, open(mask_file, 'a', encoding='utf-8') as mask_f:
            for k, v in zip(keys, values):
                env_file.write(f"{k}={v}\n")
                mask_f.write(f'echo "::add-mask::{v}"\n')


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
    def add_beijing_timezone(dt: datetime) -> datetime:
        """
        为数据库中存储的北京时间添加 tzinfo
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone(timedelta(hours=8)))
        return dt

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
    CLogger.setup_logger()
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', choices=["PostProcess", 'task2'], required=True, help='任务名称')
    args = parser.parse_args()

    # 任务全部完成的后处理
    if args.task == "PostProcess":
        try:
            Utils.post_process()
        except Exception as e:
            logging.error(e)

