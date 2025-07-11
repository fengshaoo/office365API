import logging

from config import Config


class APIErrorSet:
    """
    用于统计调用失败的集合
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._error_flag = False
        self._error_set = set()
        self._count = 0

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, num):
        self._count = num

    def add_error(self, error):
        """添加一个错误信息，自动去重"""
        self.logger.info("插入API调用错误集合")
        if error not in self._error_set:
            self._error_set.add(error)
            self._count += 1
            if not self._error_flag:
                self._error_flag = True

    def clear(self):
        """清空错误集合"""
        self._error_set.clear()
        self._count = 0
        self._error_flag = False

    def to_list(self):
        """将错误集合转换成列表并返回"""
        return list(self._error_set)

    def get_err_urls(self):
        """根据序号输出格式化后的URL列表"""
        err_list = self.to_list()
        if Config.API_LIST is None:
            return err_list

        err_url_list = []
        for idx in err_list:
            if 0 <= idx < len(Config.API_LIST):
                url = Config.API_LIST[idx]
                if Config.API_PREFIXES is not None:
                    for prefix in Config.API_PREFIXES:
                        if url.startswith(prefix):
                            url = url[len(prefix):]
                            break
                err_url_list.append(url)
        return err_url_list

    @property
    def has_error(self):
        return self._error_flag

    def __str__(self):
        return f"errors: {self._error_set}, count: {self._count}, flag: {self._error_flag}"