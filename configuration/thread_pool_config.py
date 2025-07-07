from concurrent.futures import ThreadPoolExecutor, Future
import threading
import atexit
import logging

class ThreadPoolManager:
    _instance_lock = threading.Lock()
    _instance = None

    def __init__(self, max_workers=10, thread_name_prefix="thread-pool"):
        self.logger = logging.getLogger(self.__class__.__name__)

        if not hasattr(self, 'executor'):
            self.executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix=thread_name_prefix
            )
            self.logger.info(f"初始化线程池: max_workers={max_workers}, prefix={thread_name_prefix}")
            atexit.register(self._shutdown_at_exit)

    @classmethod
    def get_instance(cls, max_workers=10, thread_name_prefix="thread-pool"):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(max_workers, thread_name_prefix)
        return cls._instance

    def submit(self, fn, *args, **kwargs) -> Future:
        """
        提交一个任务到线程池。
        返回一个 Future 对象，可用于追踪任务状态或结果。
        """
        try:
            future = self.executor.submit(fn, *args, **kwargs)
            return future
        except RuntimeError as e:
            self.logger.error(f"任务提交失败: {e}")
            raise

    def shutdown(self, wait=True):
        """
        主动关闭线程池（阻塞或非阻塞）。
        通常建议只在程序关闭时调用。
        """
        self.logger.info("关闭线程池")
        self.executor.shutdown(wait=wait)

    def _shutdown_at_exit(self):
        """
        注册在程序退出时自动关闭线程池，防止资源泄露。
        """
        self.shutdown(wait=True)