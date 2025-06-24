# -*- coding: UTF-8 -*-
import time
import logging
from datetime import datetime

from config import Config
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



    def run(self):
        self.logger.info("--->成功执行到调用步骤<---")



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
