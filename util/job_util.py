import asyncio
from datetime import datetime

from croniter import croniter

from astrbot.api import logger


class CronSchedulerUtil:
    """ cron 定时任务调度"""

    def __init__(self):
        self.tasks = []  # 任务列表
        self.task_handles = []  # 任务句柄存储(启动的任务)

    def add_task(self, job_func, cron_expr, *args, **kwargs) -> None:
        """添加定时任务

        Args:
            job_func: 函数名
            cron_expr: cron 表达式
            *args: 方法参数
            **kwargs: 方法关键字参数
        """
        self.tasks.append((job_func, cron_expr, args, kwargs))
        self._start_single_task(job_func, cron_expr, *args, **kwargs)

    async def stop(self) -> None:
        """停止所有定时任务"""
        for handle in self.task_handles:
            handle.cancel()
        # 等待所有任务终止
        await asyncio.gather(*self.task_handles, return_exceptions=True)
        self.task_handles.clear()

    def _start_single_task(self, job_func, cron_expr, *args, **kwargs) -> None:
        """启动单个任务调度器

        Args:
            job_func: 函数名
            cron_expr: cron 表达式
            *args: 方法参数
            **kwargs: 方法关键字参数
        """
        handle = asyncio.create_task(self._cron_worker(job_func, cron_expr, *args, **kwargs))
        self.task_handles.append(handle)

    @staticmethod
    async def _cron_worker(job_func, cron_expr, *args, **kwargs) -> None:
        """实际执行调度的协程

        Args:
            job_func: 函数名
            cron_expr: cron 表达式
            *args: 方法参数
            **kwargs: 方法关键字参数
        """
        cron = croniter(cron_expr, datetime.now())

        while True:
            try:
                # 计算下次执行时间
                next_time = cron.get_next(datetime)
                current_time = datetime.now()
                wait_seconds = (next_time - current_time).total_seconds()
                # 精准等待
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                asyncio.create_task(job_func(*args, **kwargs))  # 执行任务（并发执行）
            except asyncio.CancelledError:
                break  # 任务被取消时退出
            except Exception as e:
                logger.error(f"定时任务执行失败: {e}")
                await asyncio.sleep(1)  # 错误冷却时间
