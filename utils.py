import argparse
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
        connection = None
        # 检查是否配置数据库
        if Config.DATABASE_URL is None:
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
            db_url = make_url(f"mysql+pymysql://{Config.DATABASE_URL}")
            engine = create_engine(db_url, pool_pre_ping=True)
            Session = sessionmaker(bind=engine)
            session = Session()
            with connection.cursor() as cursor:
                sql = "UPDATE job_detail SET job_status=%s WHERE id=%s"
                cursor.execute(sql, (1, job_id))
                connection.commit()
                logging.info(f"成功更新 job_id={job_id} 的任务状态为 success")
        except Exception as e:
            raise BasicException(ErrorCode.UPDATE_DATABASE_ERROR, extra=e)
        finally:
            if connection:
                connection.close()

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

