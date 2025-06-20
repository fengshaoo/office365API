# -*- coding: UTF-8 -*-
import requests
import time
import random
import logging

from config import Config
from utils import Utils


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

    # 数据初始化
    def __init__(self):
        super().__init__()

        # self.headers = {'Content-Type': 'application/x-www-form-urlencoded'
        #                 }
        # self.header_wechar = {
        #     'Content-Type': 'application/json'}

    def __enter__(self):
        # 日志初始化
        # TODO 数据库读取本次调用的日志ID
        code = "fengshao"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"auto_run_{code}.log", mode='w', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger(__name__)

        logger.info("调用开始执行")
        return self

    # 调用函数
    def runapi(self, apilist, a, c):
        access_token = Config.ACCESS_TOKEN_LIST[a-1]
        headers = {
            'Authorization': access_token,
            'Content-Type': 'application/json'
        }
        f1 = Foo()  # 实例化计数器
        for a in range(len(apilist)):
            try:
                if requests.get(Config.API_LIST[apilist[a]], headers=headers).status_code == 200:
                    print('第'+str(apilist[a])+"号api调用成功")

                    if Config.config_list['是否开启各api延时'] != 'N':
                        time.sleep(random.randint(
                            Config.config_list['api延时范围开始'], Config.config_list['api延时结束']))
                else:
                    print('第'+str(apilist[a])+"号api调用失败")
                    if c == 1:  # 仅统计一轮错误次数
                        f1.count = f1.count + 1
            except:
                print("pass")
                pass


    def fixlist(self):
        # 随机api序列
        fixed_api = [0, 1, 5, 6, 20, 21]
        # 保证抽取到outlook,onedrive的api
        ex_api = [2, 3, 4, 7, 8, 9, 10, 22, 23, 24, 25,
                  26, 27, 13, 14, 15, 16, 17, 18, 19, 11, 12]
        # 额外抽取填充的api
        fixed_api.extend(random.sample(ex_api, 6))
        random.shuffle(fixed_api)
        return fixed_api



    def run(self):
        # 实际运行
        # 首先判断token是否都能够正常工作
        run_time_temp = [0, 0, 0]  # hour minute second
        if Utils.getaccess() == -1:
            Utils.sendmessage(12, run_time_temp)
            return
        
        #self.getaccess()
        
        begin_time = time.time()  # 统计时间开始
        
        print('共'+str(Config.config_list['每次轮数'])+'轮')
        for c in range(1, Config.config_list['每次轮数']+1):
            if Config.config_list['是否启动随机时间'] == 'Y':
                time.sleep(random.randint(
                    Config.config_list['延时范围起始'], Config.config_list['结束']))
            for a in range(1, int(Config.APP_NUM)+1):
                if Config.config_list['是否开启各账号延时'] == 'Y':
                    time.sleep(random.randint(
                        Config.config_list['账号延时范围开始'], Config.config_list['账号延时结束']))
#                 if a == 1:
                print('\n'+'应用/账号 '+str(a)+' 的第'+str(c)+'轮' +
                      time.asctime(time.localtime(time.time()))+'\n')
                if Config.config_list['是否开启随机api顺序'] == 'Y':
                    print("已开启随机顺序,共12个api")
                    apilist = self.fixlist()
                    self.runapi(apilist, a, c)
                else:
                    print("原版顺序,共10个api")
                    apilist = [5, 9, 8, 1, 20, 24, 23, 6, 21, 22]
                    self.runapi(apilist, a, c)

        end_time = time.time()  # 统计时间结束
        run_time = round(end_time-begin_time)
        hour = run_time//3600
        minute = (run_time-3600*hour)//60
        second = run_time-3600*hour-60*minute

        run_times = [hour ,minute,second]  # hour minute second 
                       
        f2 = Foo()
        if f2.count != 0:
            Utils.sendmessage(f2.count, run_times)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
        # TODO 记录日志并将日志文件传输到服务器


def entrance():
    with API() as api:
        api.logger.info("调用开始执行")
        api.run()
        local_time = time.strftime('%Y-%m-%d %H:%M:%S')
        api.logger.info("执行完成，完成时间{}".format(local_time))


if __name__ == "__main__":
    entrance()
