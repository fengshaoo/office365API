

class ErrorCode:
    INIT_ENVIRONMENT_ERROR = 'INIT_ENVIRONMENT_ERROR'
    WRITE_FILE_ERROR = 'WRITE_FILE_ERROR'
    DATABASE_CONNECT_ERROR = 'DATABASE_CONNECT_ERROR'
    UPDATE_DATABASE_ERROR = 'UPDATE_DATABASE_ERROR'

    FIELD_MISSING = 'FIELD_MISSING'


    # 错误码映射表：code → (错误码, 错误信息)
    _ERROR_MAP = {
        INIT_ENVIRONMENT_ERROR: (1100, "初始化环境变量失败"),
        WRITE_FILE_ERROR: (1105, "写入 GITHUB_ENV 文件失败"),
        DATABASE_CONNECT_ERROR: (1110, "数据库连接失败"),
        UPDATE_DATABASE_ERROR: (2100, "更新数据库失败"),

        FIELD_MISSING: (2200, "字段缺失")
    }

    @classmethod
    def get_error(cls, key):
        if key not in cls._ERROR_MAP:
            return 9999, 'Unknown error'
        return cls._ERROR_MAP[key]


class BasicException(Exception):
    def __init__(self, error_key, extra=None):
        self.code, self.message = ErrorCode.get_error(error_key)
        self.detail = extra
        super().__init__(f"[{self.code}] {self.message}")

    def __str__(self):
        base_msg = f"[{self.code}] {self.message}"
        if self.detail:
            return f"{base_msg} | Detail: {self.detail}"
        return base_msg