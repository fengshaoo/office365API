import argparse
import requests
import copy
import json
import time
import random
import pymysql
import logging
import os

from config import Config


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
    def post_process():
        """
        连接 MySQL 数据库，完成任务的后处理操作
        """
        connection = None
        # 检查是否配置数据库
        if Config.DATABASE_URL is None:
            logging.warning("未配置数据库，采用本地模式")
            logging.info("任务完成，正常退出")
            return
        # 检查job_id是否设置
        job_id = os.environ.get("JOB_ID")
        if job_id is None:
            logging.error("数据库连接模式下 job_id 未找到，请检查主函数是否设置id或是否写入GITHUB_ENV文件")
            return

        try:
            # 解析数据库连接url （user:password@host:port/dbname）
            user, rest = Config.DATABASE_URL.split(':', 1)
            password, rest = rest.split('@', 1)
            host_port, dbname = rest.split('/', 1)
            host, port = host_port.split(':')

            connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=dbname,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            with connection.cursor() as cursor:
                sql = "UPDATE job_detail SET job_status=%s WHERE id=%s"
                cursor.execute(sql, (1, job_id))
                connection.commit()
                logging.info(f"成功更新 job_id={job_id} 的任务状态为 success")
        except Exception as e:
            logging.error(f"更新数据库出错: {e}")
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

    # TODO 编写生成id方法
    @staticmethod
    def generate_id():

        return 1

    @staticmethod
    def parse_log_server():
        # 检查是否配置数据库
        if Config.LOG_SERVER_URL is None:
            logging.warning("未配置日志服务器，采用本地模式")
            return

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
                    "user",
                    "host",
                    "file_path"
                ]
            )
        except Exception as e:
            logging.error(f"写入GitHub ENV工作流文件失败：{e}")




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', choices=["PostProcess", 'task2'], required=True, help='任务名称')
    args = parser.parse_args()

    # 任务全部完成的后处理
    if args.task == "PostProcess":
        Utils.post_process()