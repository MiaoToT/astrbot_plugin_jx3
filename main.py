from datetime import datetime
from typing import Callable, Optional, List, TypedDict

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import BaseMessageComponent, Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from .util import AsyncHttpUtil, CronSchedulerUtil
from .util import image_util


class SchedulerStatus(TypedDict):
    """用于存储部分定时任务状态"""
    last_server_status: Optional[dict]  # 上一次服务器状态
    last_skill_info_id: Optional[str]  # 上一次技改信息id


@register("jx3", "MiaoToT", "剑三 API", "1.0")
class Jx3Plugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self._plugin_config = config
        self._api_params = {
            "server": config["server"],
            "token": config["token"],
            "ticket": config["ticket"],
            "nickname": "喵喵",
        }
        self._scheduler_status: SchedulerStatus = {  # 用于存储部分定时任务状态
            "last_server_status": None,
            "last_skill_info_id": None,
        }
        self._host = config["host"]  # 剑三 API 调用域名
        self._subscriber = config["subscriber"]  # 定时任务需要发送的群组
        self._scheduler = CronSchedulerUtil()
        # self._scheduler.add_task(self.server_on_status, "*/20 8-18 * * *")  # 开服检测
        # self._scheduler.add_task(self.server_off_status, "0 5 * * *")  # 维护检测
        self._scheduler.add_task(self.skill_info, "0 12 * * *")  # 技改公告查询

    @filter.command_group("剑三")
    def jx3(self):
        """剑三命令组"""
        pass

    @jx3.command("日常")
    @filter.llm_tool(name="jx3_daily")
    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.permission_type(filter.PermissionType.MEMBER)
    async def daily(self, event: AstrMessageEvent):
        """预测今天的日常任务"""
        yield await self.result_handler("/data/active/calendar",
                                        lambda data: [image_util.daily_info_image(data)],
                                        event, {"num": 0})

    @jx3.command("日历")
    @filter.llm_tool(name="jx3_calendar")
    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.permission_type(filter.PermissionType.MEMBER)
    async def calendar(self, event: AstrMessageEvent):
        """预测前后共7天的日常任务"""
        yield await self.result_handler("/data/active/list/calendar",
                                        lambda data: [image_util.calender_image(data)],
                                        event, {"num": 7})

    @jx3.command("楚天社", alias={"云从社", "披风会"})
    @filter.llm_tool(name="jx3_celebs")
    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.permission_type(filter.PermissionType.MEMBER)
    async def celebs(self, event: AstrMessageEvent):
        """获取侠行事件|楚天社,云从社,披风会"""
        yield await self.result_handler("/data/active/celebs",
                                        lambda data: [image_util.schedule_image(data)],
                                        event, {"name": event.get_message_str().split(" ")[1]})

    @jx3.command("令牌")
    @filter.llm_tool(name="jx3_renew_ticket")
    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def renew_ticket(self, event: AstrMessageEvent, ticket: str):
        """推栏令牌更新"""
        self._plugin_config["ticket"] = ticket
        self._plugin_config.save_config()
        self._api_params["ticket"] = ticket
        yield event.plain_result("更新成功")

    async def skill_info(self):
        """技改信息"""

        def data_handler(data: dict) -> List[BaseMessageComponent]:
            api_skill_id = data[0]["id"]
            if self._scheduler_status["last_skill_info_id"] == api_skill_id:
                return []
            is_init = self._scheduler_status["last_skill_info_id"] is None  # 是否第一次初始化
            self._scheduler_status["last_skill_info_id"] = api_skill_id
            # 第一次初始化不发送消息
            if is_init:
                return []
            skill_title = data[0]["title"]
            skill_url = data[0]["url"]
            return [Plain(f"{skill_title}:\n{skill_url}")]

        await self.result_handler("/data/skills/records", data_handler)

    async def server_on_status(self):
        """开服检测:每天8-18点20分钟一次检测直到开服"""
        last_status = self._scheduler_status["last_server_status"]
        # 检测状态为开服则不再进行检测
        if last_status is not None and last_status["status"] == 1:
            return

        def data_handler(data: dict) -> List[BaseMessageComponent]:
            api_time = data["time"]  # api 服务器状态变更时间
            is_init = self._scheduler_status["last_server_status"] is None  # 是否第一次初始化
            self._scheduler_status["last_server_status"] = {
                "time": api_time,
                "status": data["status"],  # api 服务器状态
            }
            # 第一次初始化不发送消息
            if is_init:
                return []
            time = datetime.fromtimestamp(api_time).strftime("%H:%M")
            server_name = self._api_params["server"]
            return [Plain(f"{server_name} 在{time}开服啦 ε(*′･∀･｀)зﾞ")]

        await self.result_handler("/data/server/check", data_handler)

    async def server_off_status(self):
        """维护检测:每天早上5点检测一次"""

        def data_handler(data: dict) -> List[BaseMessageComponent]:
            self._scheduler_status["last_server_status"] = {
                "time": data["time"],  # api返回时间
                "status": data["status"],  # api返回状态
            }
            return []

        await self.result_handler("/data/server/check", data_handler)

    async def result_handler(
            self,
            path_name: str,
            success_handler: Callable[[dict], List[BaseMessageComponent]],
            event: AstrMessageEvent = None,
            params: Optional[dict] = None
    ) -> None:
        """获取消息返回结果

        Args:
            path_name (str): 路径名
            success_handler (Callable[[dict], Awaitable[List[BaseMessageComponent]]): 请求成功时需要执行的函数
            event (AstrMessageEvent): 消息事件
            params (Optional[dict]): 变化部分请求参数
        """
        try:
            http_result = await AsyncHttpUtil.post(self._get_url(path_name), self._get_params(params))
        except Exception as e:
            logger.warning(f"API请求异常: {str(e)}")
            await self._return_error_msg(event)
            return None

        if http_result["code"] != 200:
            logger.warning(f"API请求返回结果异常：{http_result['msg']}")
            await self._return_error_msg(event, http_result['msg'])
            return None

        try:
            data = success_handler(http_result["data"])  # 根据回调方法处理数据
            # 数据为空不发送消息
            if not data:
                return None
            result_msg_chain = MessageChain()
            result_msg_chain.chain.extend(data)
            # event存在代表是指令触发，否则是定时任务触发，定时任务触发则给所有指定的群组发消息
            groups = self._subscriber if event is None else [event.unified_msg_origin]
            for group_id in groups:
                await self.context.send_message(group_id, result_msg_chain)
        except Exception as e:
            logger.exception(e)
            await self._return_error_msg(event)
        return None

    async def _return_error_msg(self, event: AstrMessageEvent = None, error_msg: str = None) -> None:
        """错误信息返回

        Args:
            event: 主动请求事件
        """
        if event is None:
            return
        result_msg_chain = MessageChain()
        result_msg_chain.message(error_msg if error_msg is not None else "未知错误")
        await self.context.send_message(event.unified_msg_origin, result_msg_chain)

    def _get_url(self, path_name: str) -> str:
        """给路径增加域名信息

        Args:
            path_name (str): 路径名

        Returns:
            _type_: 完整 URL
        """
        return self._host + path_name

    def _get_params(self, params: dict) -> dict:
        """将固定的请求参数和每个接口变化的请求参数合并返回

        Args:
            params (dict): 变化部分请求参数

        Returns:
            dict: 合并的请求参数
        """
        result = self._api_params.copy()
        if params:
            result.update(params)
        return result
