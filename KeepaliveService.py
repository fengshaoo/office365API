# keep_alive.py
# 完整的 Office365 开发者订阅续签脚本，集中管理 API 列表，包含失败模拟策略、代理模拟、随机延时等。
# 通过环境变量配置 Azure AD 凭据和其他参数。

import requests
import random
import time
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable

# ----------------------- 配置区域 -----------------------
# 通过环境变量读取配置，适合在 CI/CD（如 GitHub Actions）中使用 Secrets 注入。
CLIENT_ID = os.getenv('CLIENT_ID')  # Azure 应用 Client ID
CLIENT_SECRET = os.getenv('CLIENT_SECRET')  # Azure 应用 Client Secret
TENANT_ID = os.getenv('TENANT_ID')  # Azure AD 租户 ID
REFRESH_TOKEN = os.getenv('REFRESH_TOKEN')  # OAuth2 刷新令牌
USER_EMAIL = os.getenv('USER_EMAIL')  # 用于 sendMail 场景的目标邮箱

# 代理列表（可选）：若需模拟真实网络环境或绕过网络限制，可在环境变量中提供代理地址列表，或留空。
# 格式示例：HTTP_PROXY_LIST="http://proxy1:port,http://proxy2:port"
PROXY_LIST = os.getenv('HTTP_PROXY_LIST', '')
PROXIES = [p.strip() for p in PROXY_LIST.split(',') if p.strip()]

# User-Agent 列表，用于模拟不同设备或浏览器
USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/114.0 Safari/537.36",
]

# 随机延迟参数
MAX_START_DELAY = int(os.getenv('MAX_START_DELAY', '300'))  # 最多延迟 300 秒
REQUEST_DELAY_MIN = int(os.getenv('REQUEST_DELAY_MIN', '1'))
REQUEST_DELAY_MAX = int(os.getenv('REQUEST_DELAY_MAX', '5'))
# 失败模拟概率（整体），控制在 0.05~0.1
FAILURE_SIMULATION_PROB = float(os.getenv('FAILURE_SIMULATION_PROB', '0.08'))
# 超时模拟概率
TIMEOUT_SIMULATION_PROB = float(os.getenv('TIMEOUT_SIMULATION_PROB', '0.03'))
# 请求超时秒数
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
# 最大重试次数与基础退避
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
BASE_BACKOFF = int(os.getenv('BASE_BACKOFF', '5'))

# ----------------------- 日志配置 -----------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ----------------------- 工具函数 -----------------------
def choose_proxy() -> Optional[Dict[str, str]]:
    """随机选择一个代理，如果没有配置则返回 None"""
    if not PROXIES:
        return None
    proxy = random.choice(PROXIES)
    return {'http': proxy, 'https': proxy}

def random_user_agent() -> str:
    return random.choice(USER_AGENT_LIST)

# ----------------------- Token 管理 -----------------------
_access_token: Optional[str] = None
_expires_at: float = 0

def get_access_token() -> Optional[str]:
    global _access_token, _expires_at
    now = time.time()
    if _access_token and now < _expires_at - 60:
        return _access_token
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        logger.error("缺少 Azure AD 凭据或刷新令牌，请检查环境变量设置。")
        return None
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN,
        'scope': 'https://graph.microsoft.com/.default'
    }
    # 模拟超时
    try:
        if random.random() < TIMEOUT_SIMULATION_PROB:
            raise requests.exceptions.Timeout("模拟超时获取 token")
        resp = requests.post(token_url, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout as e:
        logger.warning(f"获取 Access Token 超时: {e}")
        return None
    except Exception as e:
        logger.error(f"获取 Access Token 异常: {e}")
        return None
    if resp.status_code != 200:
        logger.error(f"获取 Access Token 失败，状态码: {resp.status_code}, 响应: {resp.text}")
        return None
    result = resp.json()
    _access_token = result.get('access_token')
    expires_in = result.get('expires_in', 0)
    _expires_at = now + int(expires_in)
    logger.info(f"获取新的 Access Token，有效期 {expires_in} 秒")
    # 新 refresh_token 提示持久化
    new_rt = result.get('refresh_token')
    if new_rt and new_rt != REFRESH_TOKEN:
        logger.info("服务器返回新的 Refresh Token，请持久化保存以便下次使用。")
    return _access_token

# ----------------------- 请求执行与重试 -----------------------
def execute_request(method: str, url: str, headers: Dict[str, str], **kwargs) -> Optional[requests.Response]:
    """执行 HTTP 请求，包含随机失败模拟、重试、代理、随机 User-Agent"""
    for attempt in range(1, MAX_RETRIES + 1):
        # 随机延迟
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)
        # 随机代理
        proxies = choose_proxy()
        # 随机 User-Agent
        headers['User-Agent'] = random_user_agent()
        # 失败模拟：小概率删除 Authorization 或制造错误
        simulate = random.random() < FAILURE_SIMULATION_PROB
        sim_missing_auth = simulate and random.random() < 0.3  # 30% 情况下模拟缺失 Header
        sim_rate_limit = simulate and not sim_missing_auth and random.random() < 0.5  # 模拟 429
        sim_bad_request = simulate and not sim_missing_auth and not sim_rate_limit  # 模拟 400
        req_headers = headers.copy()
        if sim_missing_auth:
            req_headers.pop('Authorization', None)
            logger.info("模拟缺少 Authorization header")
        try:
            if sim_rate_limit:
                # 模拟 429
                logger.info("模拟 429 Too Many Requests 错误")
                raise requests.exceptions.HTTPError("模拟 429", response=_mock_response(429))
            if sim_bad_request:
                # 模拟 400 错误
                logger.info("模拟 400 Bad Request 错误")
                raise requests.exceptions.HTTPError("模拟 400", response=_mock_response(400))
            # 正常请求
            resp = requests.request(method, url, headers=req_headers, timeout=REQUEST_TIMEOUT, proxies=proxies, **kwargs)
        except requests.exceptions.Timeout as e:
            logger.warning(f"第 {attempt} 次请求超时: {e}")
            _wait_retry(attempt, None)
            continue
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            logger.warning(f"第 {attempt} 次请求 HTTPError: {status}")
            if status in (429, 500, 502, 503, 504):
                retry_after = _get_retry_after(e.response)
                _wait_retry(attempt, retry_after)
                continue
            else:
                logger.error(f"请求失败且不重试，状态码: {status}")
                return None
        except Exception as e:
            logger.error(f"第 {attempt} 次请求异常: {e}")
            _wait_retry(attempt, None)
            continue
        # 检查响应
        if resp.status_code >= 200 and resp.status_code < 300:
            logger.info(f"请求成功: {method} {url} -> {resp.status_code}")
            return resp
        else:
            status = resp.status_code
            logger.warning(f"请求返回非2xx: {status}")
            if status in (429, 500, 502, 503, 504):
                retry_after = _get_retry_after(resp)
                _wait_retry(attempt, retry_after)
                continue
            else:
                logger.error(f"请求失败且不重试，状态码: {status}, 响应: {resp.text}")
                return None
    logger.error(f"请求多次重试后仍然失败: {method} {url}")
    return None


def _mock_response(status_code: int) -> requests.Response:
    """生成一个伪造 Response 对象，仅包含状态码"""
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = b""
    resp.headers = {}
    return resp


def _get_retry_after(resp: Optional[requests.Response]) -> Optional[int]:
    if resp is not None and 'Retry-After' in resp.headers:
        try:
            return int(resp.headers['Retry-After'])
        except:
            return None
    return None


def _wait_retry(attempt: int, retry_after: Optional[int]):
    if retry_after:
        wait = retry_after
    else:
        wait = BASE_BACKOFF * (2 ** (attempt - 1))
    logger.info(f"等待 {wait} 秒后重试")
    time.sleep(wait)

# ----------------------- API 列表管理 -----------------------
# 所有 API 操作集中管理，url 以 / 开头，实际调用时在前面加 base
BASE_URL = "https://graph.microsoft.com/v1.0"

# 定义 API 项，支持静态 URL 或动态生成 URL 和 body
class ApiOp:
    def __init__(self,
                 category: str,
                 name: str,
                 method: str,
                 url: Optional[str] = None,
                 url_func: Optional[Callable[[], str]] = None,
                 body_func: Optional[Callable[[], Any]] = None,
                 required: bool = False):
        self.category = category
        self.name = name
        self.method = method
        self.url = url
        self.url_func = url_func
        self.body_func = body_func
        self.required = required

    def get_full_url(self) -> str:
        if self.url_func:
            return BASE_URL + self.url_func()
        elif self.url:
            return BASE_URL + self.url
        else:
            raise ValueError("API URL 未定义")

    def get_body(self) -> Any:
        if self.body_func:
            return self.body_func()
        return None

# 构建 API 列表
API_LIST: List[ApiOp] = []

# 身份与用户信息类（固定调用）
API_LIST.append(ApiOp(category='identity', name='get_user', method='GET', url='/me', required=True))
# 读取邮件
API_LIST.append(ApiOp(category='mail', name='get_messages', method='GET', url='/me/messages?$top=5', required=True))
# 读取日历事件
API_LIST.append(ApiOp(category='calendar', name='get_calendar_events', method='GET', url='/me/calendar/events?$top=5', required=True))

# 可选操作：邮件处理
def body_send_mail():
    subject = f"KeepAlive 邮件 {datetime.utcnow().isoformat()}"
    return {
        'message': {
            'subject': subject,
            'body': {'contentType': 'Text', 'content': '这是一封 KeepAlive 测试邮件。'},
            'toRecipients': [{'emailAddress': {'address': USER_EMAIL}}]
        },
        'saveToSentItems': 'false'
    }
API_LIST.append(ApiOp(category='mail', name='send_mail', method='POST', url='/me/sendMail', body_func=body_send_mail))

# 可选操作：日历处理
def body_create_event():
    now = datetime.utcnow()
    start = (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    end = (now + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {
        'subject': f'KeepAlive Event {now.isoformat()}',
        'body': {'contentType': 'Text', 'content': 'KeepAlive event'},
        'start': {'dateTime': start, 'timeZone': 'UTC'},
        'end': {'dateTime': end, 'timeZone': 'UTC'},
    }
API_LIST.append(ApiOp(category='calendar', name='create_event', method='POST', url='/me/events', body_func=body_create_event))

# 可选操作：OneDrive 文件处理
def url_upload_file():
    # 随机文件名
    file_name = f"keepalive_{int(time.time())}.txt"
    return f"/me/drive/root:/{file_name}:/content"

def body_upload_file():
    return f"KeepAlive at {datetime.utcnow().isoformat()}".encode('utf-8')
API_LIST.append(ApiOp(category='onedrive', name='upload_file', method='PUT', url_func=url_upload_file, body_func=body_upload_file))

# 可选操作：SharePoint 处理（示例：读取根站点列表）
API_LIST.append(ApiOp(category='sharepoint', name='get_sp_lists', method='GET', url='/sites/root/lists'))

# 可选：可再添加更多类别操作，如 Contacts、Teams 等

# ----------------------- 执行流程 -----------------------
def main():
    logger.info("启动 KeepAlive 脚本，集中管理 API 列表模式")
    # 随机初始延迟
    start_delay = random.randint(0, MAX_START_DELAY)
    logger.info(f"随机初始延迟 {start_delay} 秒后开始")
    time.sleep(start_delay)

    token = get_access_token()
    if not token:
        logger.error("无法获取 Access Token，退出")
        return

    headers_base = {'Authorization': f'Bearer {token}'}

    # 1. 固定调用：身份与用户信息、读取邮件、读取日历事件
    for api in API_LIST:
        if api.required:
            url = api.get_full_url()
            method = api.method
            body = api.get_body()
            hdr = headers_base.copy()
            if body is not None:
                hdr['Content-Type'] = 'application/json' if api.method in ('POST', 'PATCH') else hdr.get('Content-Type', '')
            logger.info(f"固定调用: {api.name}")
            execute_request(method, url, hdr, json=body if isinstance(body, dict) else None, data=body if isinstance(body, (bytes, bytearray)) else None)

    # 2. 随机调用：从每个类别随机选择若干操作
    # 分组
    categories = {}
    for api in API_LIST:
        if not api.required:
            categories.setdefault(api.category, []).append(api)
    chosen_ops: List[ApiOp] = []
    # 对每个类别，随机决定是否执行及数量
    for cat, ops in categories.items():
        # 50% 概率执行该类别操作
        if random.random() < 0.5:
            # 从该类别中随机选 1 个或多个
            count = random.randint(1, len(ops))
            chosen = random.sample(ops, count)
            chosen_ops.extend(chosen)
            logger.info(f"从类别 {cat} 中选取 {count} 个操作")
        else:
            logger.info(f"跳过类别 {cat} 的操作")
    # 打乱顺序
    random.shuffle(chosen_ops)
    # 执行选中操作
    for api in chosen_ops:
        url = api.get_full_url()
        method = api.method
        body = api.get_body()
        hdr = headers_base.copy()
        if body is not None:
            hdr['Content-Type'] = 'application/json' if isinstance(body, dict) else 'application/octet-stream'
        logger.info(f"随机调用: {api.category} - {api.name}")
        execute_request(method, url, hdr, json=body if isinstance(body, dict) else None, data=body if isinstance(body, (bytes, bytearray)) else None)

    logger.info("KeepAlive 脚本执行完成")

if __name__ == '__main__':
    main()
