import requests
import copy
import json
import time
import random

from config import Config


class Utils:
    """
    工具类
    """

    def sendmessage(self, i, run_times):
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

    def getmstoken(self, client_id, client_secret, ms_token):
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
    def getaccess(self):
        # 一次性获取access_token，降低获取率
        for a in range(1, int(Config.APP_NUM) + 1):
            client_id = Config.CLIENT_ID
            client_secret = Config.CLIENT_SECRET
            ms_token = Config.REFRESH_TOKEN
            Config.ACCESS_TOKEN_LIST[a - 1] = self.getmstoken(client_id, client_secret, ms_token)
            if Config.ACCESS_TOKEN_LIST[a - 1] == -1:
                return -1