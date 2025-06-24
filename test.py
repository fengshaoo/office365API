import logging
from datetime import datetime

from dao.job_detail_service import JobDetailService
from errorInfo import BasicException, ErrorCode
from pojo.job_detail import JobDetail

if __name__ == "__main__":
    # entrance()

    # 数据库
    databast_url = "office365:baiying.com153@172.207.159.214:3306/auto_api_db"

    user, rest = databast_url.split(':', 1)
    password, rest = rest.split('@', 1)
    host_port, dbname = rest.split('/', 1)
    host, port = host_port.split(':')

    logging.info(f"user:{user}, password:{password}, host:{host}, porn:{port}, dbname:{dbname}")

    # 日志服务器
    log_service_url = "fengshao@172.207.159.214//home/fengshao/github_action/auto_api/logs"
    user, rest = log_service_url.split('@', 1)
    host, file_path = rest.split('/', 1)
    logging.info(f"user:{user}, host:{host}, file_path:{file_path}")

    try:
        job_detail_service = JobDetailService()
    except Exception as e:
        raise BasicException(ErrorCode.DATABASE_CONNECT_ERROR, extra=e)

    # 初始化本次任务的数据库
    new_job = JobDetail(
        id=1234567899333543,
        start_time = datetime.now(),
        end_time = None,
        process = 'init',
        status = 'running',
        job_status = 0
    )
    job_detail_service.create_job(new_job)