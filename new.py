# -*- coding: UTF-8 -*-
import time
import logging
import pymysql

from config import Config
from utils import Utils
from errorInfo import ErrorCode
from errorInfo import BasicException
from logger_config import setup_logger


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

        # 配置日志服务器连接
        if Config.LOG_SERVER_URL is None:
            self.logger.warning("未配置日志服务器，采用本地模式，该模式下无日志存档")
        else:
            try:
                # 解析日志服务器url （user@host/file_path）
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
                # 解析数据库连接url （user:password@host:port/dbname）
                user, rest = Config.DATABASE_URL.split(':', 1)
                password, rest = rest.split('@', 1)
                host_port, dbname = rest.split('/', 1)
                host, port = host_port.split(':')

                self.connection = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=dbname,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
            except Exception as e:
                raise BasicException(ErrorCode.DATABASE_CONNECT_ERROR, extra=e)
        return self



    def run(self):
        pass



    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
        return False


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
