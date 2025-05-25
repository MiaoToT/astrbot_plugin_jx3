import asyncio
import os
import random
from typing import Dict, Optional

import aiohttp

from astrbot.api import logger


class AsyncHttpUtil:
    """异步HTTP复用工具类(单例)"""

    _session: Optional[aiohttp.ClientSession] = None
    _session_lock = asyncio.Lock()
    _timeout = aiohttp.ClientTimeout(total=10)  # 默认超时时间10s
    _max_retries = 3  # 默认重试次数
    _base_retry_delay = 0.5  # 默认重试等待基数时间 0.5s

    def __init__(self):
        """禁止外部实例化"""
        raise RuntimeError("禁止实例化，请直接使用类方法")

    @classmethod
    async def close(cls):
        """关闭全局会话"""
        async with cls._session_lock:
            if cls._session and not cls._session.closed:
                await cls._session.close()
                logger.info("关闭全局会话 PID:%s", os.getpid())

    @classmethod
    async def _request(
            cls,
            method: str,
            url: str,
            params: Optional[Dict] = None,
            data: Optional[Dict] = None,
            json: Optional[Dict] = None,
            headers: Optional[Dict] = None,
    ) -> Optional[dict]:
        """内部请求处理器，支持重试机制

        Args:
            method (str): HTTP方法（GET/POST等）
            url (str): 请求地址
            params (Optional[Dict]): URL查询参数
            data (Optional[Dict]): 表单数据
            json (Optional[Dict]): JSON数据
            headers (Optional[Dict]): 自定义请求头

        Raises:
            aiohttp.ClientResponseError: 网络或HTTP协议错误

        Returns:
            Optional[aiohttp.ClientResponse]: 成功时返回响应JSON解析结果，失败返回None
        """

        # 确保会话已创建（线程安全）
        async with cls._session_lock:
            if cls._session is None or cls._session.closed:
                cls._session = aiohttp.ClientSession(
                    timeout=cls._timeout, connector=aiohttp.TCPConnector(limit_per_host=100)
                )
                logger.info("创建全局会话 PID:%s", os.getpid())

        retries = 0  # 当前重试次数
        while retries < cls._max_retries:
            try:
                async with cls._session.request(
                        method, url, params=params, data=data, json=json, headers=headers
                ) as resp:
                    if not 200 <= resp.status < 300:
                        text = await resp.text()
                        raise aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=resp.status, message=text
                        )
                    return await resp.json()
            except (
                    aiohttp.ClientConnectionError,
                    aiohttp.ClientPayloadError,
                    asyncio.TimeoutError,
            ) as e:  # 限定可重试异常
                # 指数退避+随机抖动请求延迟
                delay = cls._base_retry_delay * (2 ** retries) + random.uniform(0, 0.1)
                logger.warning("请求失败[%s]，%.2f秒后重试: %s", url, delay, str(e))
                await asyncio.sleep(delay)
                retries += 1
            except Exception as e:  # 非预期异常直接抛出
                logger.error("非重试类型异常: %s", str(e))
                raise
        logger.warning("请求失败已达最大重试次数: %s", str(url))
        return None

    @classmethod
    async def get(cls, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None):
        """发起GET请求

        Args:
            url (str): 请求URL
            params (Optional[Dict]): URL查询参数
            headers (Optional[Dict]): 自定义请求头

        Returns:
            _type_: 响应JSON数据
        """
        return await cls._request("GET", url, params=params, headers=headers)

    @classmethod
    async def post(
            cls, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None, headers: Optional[Dict] = None
    ):
        """发起POST请求

        Args:
            url (str): 请求URL
            data (Optional[Dict]): 表单数据
            json (Optional[Dict]): JSON格式数据
            headers (Optional[Dict]): 自定义请求头

        Returns:
            _type_: 响应JSON数据
        """
        return await cls._request("POST", url, data=data, json=json, headers=headers)
