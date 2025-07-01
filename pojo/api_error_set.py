class APIErrorSet:
    """
    用于统计调用失败的集合
    """

    def __init__(self):
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

    @property
    def has_error(self):
        return self._error_flag

    def __str__(self):
        return f"errors: {self._error_set}, count: {self._count}, flag: {self._error_flag}"