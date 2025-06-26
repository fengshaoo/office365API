import logging
import os

from configuration.filter import NoParamsFilter
from errorInfo import BasicException, ErrorCode


class Config:
    """
    配置类
    存放所有的配置项
    """
    # 必配项目 -------------------------------------------------------
    CLIENT_ID = None                # Azure 应用 Client ID
    CLIENT_SECRET = None            # Azure 应用 Client Secret
    # TENANT_ID = None                # Azure AD 租户 ID
    MS_TOKEN = None                 # OAuth2 刷新令牌
    GH_TOKEN = None                 # GitHub token
    # ---------------------------------------------------------------

    # 选配项目 -------------------------------------------------------
    LOG_SERVER_URL = None           # 日志服务器连接属性,格式:user@host/file_path
    DATABASE_URL = None             # 数据库连接属性,格式:user:password@host:port/dbname

    # 信息发送配置
    USER_EMAIL = None               # 用于 sendMail 场景的目标邮箱
    TELEGRAM_TOKEN = None           # telegram 用户token
    TELEGRAM_CHAT_ID = None         # 消息群组id
    TELEGRAM_MESSAGE_STATUS = True  # Telegram通知生效状态
    # ---------------------------------------------------------------

    ENV_MODE = None                 # 运行环境
    LOG_FILENAME = "auto_run_office365" # 默认日志文件名称

    APP_NUM = 1                     # 操作账号数量（默认单账号模式）
    ENABLE_NUM = -1                 # 启用账号数量（默认-1表示全部启用）
    MIN_START_DELAY = 0             # 最小开始延迟时间（s）
    MAX_START_DELAY = 300           # 最大开始延迟时间（s）
    REQUEST_DELAY_MIN = 1           # 最小请求延迟时间（s）
    REQUEST_DELAY_MAX = 5           # 最大请求延迟时间（s）
    FAILURE_SIMULATION_PROB = 0.08  # 失败模拟概率（整体），控制在 0.05~0.1
    TIMEOUT_SIMULATION_PROB = 0.03  # 超时模拟概率
    REQUEST_TIMEOUT = 10            # 请求超时秒数
    MAX_RETRIES = 3                 # 最大重试次数
    BASE_BACKOFF = 5                # 基础退避
    # 微软校验用的重定向地址，与Azure应用配置保持一致
    REDIRECT_URI = "http://localhost:53682/"
    # 获取access_token的请求端点
    ACCESS_TOKEN_URI = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    # telegram发送通知地址
    TELEGRAM_URL = "https://api.telegram.org/bot"


    REQUEST_COMMON_HEADERS = {
        'Accept': '*/*',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',

    }

    # ----------------------- 已启用配置区域 -----------------------
    # '是否开启备用应用':'N','是否开启测试':'N'
    config_list = {
        '每次轮数': 6,
        '是否启动随机时间': 'Y', '延时范围起始': 60, '结束': 120,
        '是否开启随机api顺序': 'Y',
        '是否开启各api延时': 'N', 'api延时范围开始': 2, 'api延时结束': 5,
        '是否开启各账号延时': 'N', '账号延时范围开始': 60, '账号延时结束': 120,

        'summary': 'Office365API调用提醒',
        'contentType': 1
    }

    # 账号列表
    USER_TOKEN_DICT = {
        "MS_TOKEN": ""
    }


    # TODO 下列配置列表后续改为数据库查询
    # 代理列表：若需模拟真实网络环境或绕过网络限制，可在环境变量中提供代理地址列表，或留空。
    PROXIES = [
        # "http://proxy1:port",
        # "http://proxy2:port"
    ]

    # User-Agent 列表，用于模拟不同设备或浏览器
    USER_AGENT_LIST = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Mozilla/5.0 (Macintosh; M3 Mac OS X 14_15; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.119 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.119 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 7 Build/XXXXXX) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.115 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/138.0.7204.33 Mobile/15E148 Safari/605.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 18_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/605.1.15",
        "Mozilla/5.0 (Linux; Android 14; Pixel 7 Build/XXXXXX) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/137.0.7151.115 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; U; Android 15; zh-cn; PKK110 Build/UKQ1.231108.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/121.0.6167.71 MQQBrowser/16.3 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
    ]

    API_LIST = [
        r'https://graph.microsoft.com/v1.0/me/',
        r'https://graph.microsoft.com/v1.0/users',
        r'https://graph.microsoft.com/v1.0/me/people',
        r'https://graph.microsoft.com/v1.0/groups',
        r'https://graph.microsoft.com/v1.0/me/contacts',
        r'https://graph.microsoft.com/v1.0/me/drive/root',
        r'https://graph.microsoft.com/v1.0/me/drive/root/children',
        r'https://graph.microsoft.com/v1.0/drive/root',
        r'https://graph.microsoft.com/v1.0/me/drive',
        r'https://graph.microsoft.com/v1.0/me/drive/recent',
        r'https://graph.microsoft.com/v1.0/me/drive/sharedWithMe',
        r'https://graph.microsoft.com/v1.0/me/calendars',
        r'https://graph.microsoft.com/v1.0/me/events',
        r'https://graph.microsoft.com/v1.0/sites/root',
        r'https://graph.microsoft.com/v1.0/sites/root/sites',
        r'https://graph.microsoft.com/v1.0/sites/root/drives',
        r'https://graph.microsoft.com/v1.0/sites/root/columns',
        r'https://graph.microsoft.com/v1.0/me/onenote/notebooks',
        r'https://graph.microsoft.com/v1.0/me/onenote/sections',
        r'https://graph.microsoft.com/v1.0/me/onenote/pages',
        r'https://graph.microsoft.com/v1.0/me/messages',
        r'https://graph.microsoft.com/v1.0/me/mailFolders',
        r'https://graph.microsoft.com/v1.0/me/outlook/masterCategories',
        r'https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages/delta',
        r'https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messageRules',
        r"https://graph.microsoft.com/v1.0/me/messages?$filter=importance eq 'high'",
        r'https://graph.microsoft.com/v1.0/me/messages?$search="hello world"',
        r'https://graph.microsoft.com/beta/me/messages?$select=internetMessageHeaders&$top',
    ]

    _initialized = False

    @classmethod
    def load(cls):
        if cls._initialized:
            return

        logging.info("加载环境变量")
        # 必须配置项
        required_envs = [
            "CLIENT_ID",
            "CLIENT_SECRET",
            # "TENANT_ID",
            "MS_TOKEN",
            "GH_TOKEN",
        ]
        for key in required_envs:
            val = os.getenv(key)
            if val is None:
                raise ValueError(f"必要环境变量 `{key}` 缺失！")
            setattr(cls, key, val)  # 反射设置字段值

        # 账号相关配置
        env_app_num = os.getenv("APP_NUM")
        if env_app_num:
            if env_app_num.isdigit():
                cls.APP_NUM = int(env_app_num)
            else:
                raise BasicException(ErrorCode.INIT_ENVIRONMENT_ERROR, extra="环境变量 APP_NUM 配置错误，请检查配置项并重新启动")

        if cls.APP_NUM == 1:
            logging.info("单账号模式")
        if cls.ENABLE_NUM != -1 and cls.ENABLE_NUM > cls.APP_NUM:
            raise BasicException(
                ErrorCode.INIT_ENVIRONMENT_ERROR,
                extra="启用账号数(ENABLE_NUM)超出所配置的账号总数(APP_NUM)，请检查配置项并重新启动"
            )
        cls.USER_TOKEN_DICT["MS_TOKEN"] = cls.MS_TOKEN
        for i in range(1, cls.APP_NUM):
            key = f"MS_TOKEN_{i:02d}"
            token = os.getenv(key)
            if token is None:
                raise BasicException(
                    ErrorCode.INIT_ENVIRONMENT_ERROR,
                    extra=f"环境变量 `{key}` 缺失或账号数量(APP_NUM)配置错误，请检查配置项并重新启动，当前 APP_NUM = {cls.APP_NUM}"
                )
            cls.USER_TOKEN_DICT[key] = token

        # 选配字段设置
        cls.LOG_SERVER_URL = os.getenv("LOG_SERVER_URL", cls.LOG_SERVER_URL)
        if cls.LOG_SERVER_URL is None:
            logging.warning("未配置日志服务器，采用本地模式，该模式下无日志存档")
        cls.DATABASE_URL = os.getenv("DATABASE_URL", cls.DATABASE_URL)
        if cls.DATABASE_URL is None:
            logging.warning("未配置数据库，本地模式")

        cls.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        cls.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        cls.USER_EMAIL = os.getenv("USER_EMAIL")
        if cls.TELEGRAM_TOKEN is None or cls.TELEGRAM_CHAT_ID is None:
            cls.TELEGRAM_MESSAGE_STATUS = False
            logging.warning("未启用 Telegram 通知")
            if cls.USER_EMAIL is None:
                raise BasicException(
                    ErrorCode.INIT_ENVIRONMENT_ERROR,
                    extra="无法启用通知功能，Tel & Email 均未配置"
                )

        # 配置调试环境
        cls.ENV_MODE = os.getenv("ENV_MODE")
        # 设置 SQLAlchemy 的日志等级
        sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
        # 添加过滤器，防止输出参数
        sqlalchemy_logger.setLevel(logging.WARNING)
        if cls.ENV_MODE == "DEBUG":
            logging.warning("调试环境")
            cls.MIN_START_DELAY = 0
            cls.MAX_START_DELAY = 3
            cls.PROXIES = []
            cls.USER_AGENT_LIST = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.119 Safari/537.36",
            ]
            # !!! 设置为DEBUG级别会输出参数 !!!
            sqlalchemy_logger.setLevel(logging.INFO)

        cls._initialized = True
