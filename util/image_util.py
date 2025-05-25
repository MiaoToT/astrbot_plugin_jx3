import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import astrbot.api.message_components as comp
from astrbot.api import logger
from astrbot.core.message.components import BaseMessageComponent


def _load_font(font_size: int) -> ImageFont:
    """加载字体

    Args:
        font_size (int): 字号

    Returns:
        FreeTypeFont: 字体类型
    """
    try:
        return ImageFont.truetype(Path(__file__).parent.parent / "resource" / "LuoLiTi.ttf", font_size)
    except Exception as e:
        logger.warning(f"加载自定义字体失败：{str(e)}")

    try:
        return ImageFont.load_default().font_variant(size=font_size)
    except Exception as e:
        logger.warning(f"加载默认字体失败：{str(e)}")
        return ImageFont.load_default()


def _get_image_result(img: Image) -> BaseMessageComponent:
    """根据图片对象获取包含该图片的消息对象

    Args:
        img: 图片对象

    Returns:
        BaseMessageComponent: 返回图片消息
    """
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return comp.Image.fromBytes(buffer.getvalue())


def calender_image(data: dict) -> BaseMessageComponent:
    """剑三日历图片

    Args:
        data: 剑三日历 json

    Returns:
        BaseMessageComponent: 返回图片消息
    """
    default_colors = {
        "bg": "#F0F8FF",  # 背景
        "card_bg": "#FFFFFF",  # 卡片底色
        "border": "#87CEEB",  # 边框
        "select_border": "#FF8A59",  # 选中边框
        "date": "#006FEE",  # 日期
        "label": "#338EF7",  # 标签
        "content": "#99C7FB",  # 正文
        "highlight": "#FF69B4"  # 特殊掉落
    }
    # 初始化画布
    card_width = 200  # 卡片宽
    card_margin = 15  # 卡片外边距
    cards_per_row = 5  # 每行卡片数
    canvas_width = cards_per_row * card_width + (cards_per_row + 1) * card_margin  # 画布宽度

    # 计算布局参数
    rows = math.ceil(len(data["data"]) / cards_per_row)  # 总行数
    card_height = 180
    canvas_height = rows * card_height + (rows + 1) * card_margin  # 画布高度

    # 创建画布
    img = Image.new("RGB", (canvas_width, canvas_height), default_colors["bg"])
    ImageDraw.Draw(img)

    # 加载字体
    font_date = _load_font(18)  # 日期字体
    font_label = _load_font(15)  # 标签字体
    font_content = _load_font(15)  # 内容字体

    # 生成每个卡片
    for index, item in enumerate(data["data"]):
        # 计算卡片坐标位置
        row = index // cards_per_row  # 当前行
        col = index % cards_per_row  # 当前列
        x = card_margin + col * (card_width + card_margin)  # 卡片 x 坐标
        y = card_margin + row * (card_height + card_margin)  # 卡片 y 坐标

        # 创建卡片画布
        card = Image.new("RGB", (card_width, card_height), default_colors["bg"])
        card_draw = ImageDraw.Draw(card)

        # 如果是当天使用 select_border，否则使用 border
        card_outline_color = default_colors["border"]
        if data["today"]["date"] == item["date"]:
            card_outline_color = default_colors["select_border"]
        # 绘制卡片边框
        card_draw.rounded_rectangle(
            [(0, 0), (card_width - 1, card_height - 1)],
            radius=8,
            fill=default_colors["card_bg"],
            outline=card_outline_color,
            width=2
        )

        # 写入日期信息
        date_str = f"{item['date']}           周{item['week']}"
        card_draw.text((10, 10), date_str, fill=default_colors["date"], font=font_date)

        # 事件内容布局
        y_offset = 45
        event_items = [
            ("战场", item["battle"]),
            ("大战", item["war"]),
            ("门派", item["school"]),
            ("驰援", item["rescue"])
        ]

        # 绘制事件信息
        for label, content in event_items:
            # 绘制标签
            card_draw.text((10, y_offset), f"{label}:", fill=default_colors["label"], font=font_label)
            # 绘制内容
            card_draw.text((51, y_offset), content, fill=default_colors["content"], font=font_content)
            y_offset += 20

        # 绘制美人图
        if item.get("draw"):
            card_draw.text((10, y_offset + 10), f"美人图: {item['draw']}",
                           fill=default_colors["highlight"],
                           font=font_label)

        # 合并到主画布
        img.paste(card, (x, y))

    return _get_image_result(img)


def daily_info_image(data: dict) -> BaseMessageComponent:
    """剑三日常信息图片

    Args:
        data: 剑三日常信息 json

    Returns:
        BaseMessageComponent: 返回图片消息
    """
    default_colors = {
        "bg": "#F5F5F5",  # 改为浅灰色背景
        "card_bg": "#FFFEF6",  # 改为暖白色卡背
        "border": "#2A5CAA",  # 深蓝色边框增强对比
        "date": "#6A5ACD",  # 紫色日期更醒目
        "label": "#228B22",  # 绿色标签增加色彩对比
        "content": "#4682B4",  # 钢蓝色正文
        "highlight": "#FF4500"  # 橙色高亮加强视觉焦点
    }

    # 卡片尺寸参数
    card_width = 430
    # card_height = 720
    # 卡片高度：60 + 基本活动信息 + 美人图 + 福源 + 公共周常 + 五人周常 + 十人周常
    card_height = (60 + 150 + (30 if data["draw"] else 0) + (30 if data["luck"] else 0)
                   + ((30 + len(data["team"][0].split(";")) * 28) if data["team"] else 0)
                   + ((30 + len(data["team"][1].split(";")) * 28) if data["team"] else 0)
                   + ((30 + len(data["team"][2].split(";")) * 28) if data["team"] else 0))
    card_margin = 20
    canvas_width = card_width + card_margin * 2
    canvas_height = card_height + card_margin * 2

    # 创建画布
    img = Image.new("RGB", (canvas_width, canvas_height), default_colors["bg"])
    ImageDraw.Draw(img)

    # 创建卡片
    card = Image.new("RGB", (card_width, card_height), default_colors["card_bg"])
    card_draw = ImageDraw.Draw(card)

    # 绘制卡片边框
    card_draw.rounded_rectangle(
        [(0, 0), (card_width - 1, card_height - 1)],
        radius=10,
        outline=default_colors["border"],
        width=2
    )

    # 加载字体
    font_date = _load_font(22)
    font_label = _load_font(18)
    font_content = _load_font(16)
    font_highlight = _load_font(16)

    # 绘制日期信息
    date_str = f"{data['date']}  周{data['week']}"
    card_draw.text((20, 15), date_str, fill=default_colors["date"], font=font_date)

    y_offset = 60  # 初始内容偏移量

    # 基础活动信息
    activities = [
        ("大战", data["war"]),
        ("战场", data["battle"]),
        ("矿车", data["orecar"]),
        ("门派", data["school"]),
        ("驰援", data["rescue"])
    ]

    # 绘制基础活动
    for label, content in activities:
        # 绘制标签
        card_draw.text((25, y_offset), f"{label}: ", fill=default_colors["label"], font=font_label)
        # 绘制内容
        card_draw.text((80, y_offset), content, fill=default_colors["content"], font=font_content)
        y_offset += 30

    # 福缘
    if data["luck"]:
        card_draw.text((25, y_offset), "福缘: ", fill=default_colors["label"], font=font_label)
        card_draw.text((80, y_offset), f"✦ {' ✦ '.join(data['luck'])} ✦" if data["luck"] else "",
                       fill=default_colors["highlight"], font=font_highlight)
        y_offset += 30

    # 美人图
    if data["draw"]:
        card_draw.text((25, y_offset), "美人图: ", fill=default_colors["label"], font=font_label)
        card_draw.text((100, y_offset), data["draw"], fill=default_colors["highlight"], font=font_highlight)
        y_offset += 30

    # 团队秘境
    if data["team"]:
        ## 公共周常
        card_draw.text((25, y_offset), "公共周常: ", fill=default_colors["label"], font=font_label)
        y_offset += 30
        for item in data["team"][0].split(";"):
            card_draw.text((40, y_offset), f"• {item}", fill=default_colors["content"], font=font_content)
            y_offset += 28
        ## 五人周常
        card_draw.text((25, y_offset), "五人周常: ", fill=default_colors["label"], font=font_label)
        y_offset += 30
        for item in data["team"][1].split(";"):
            card_draw.text((40, y_offset), f"• {item}", fill=default_colors["content"], font=font_content)
            y_offset += 28
        ## 十人周常
        card_draw.text((25, y_offset), "十人周常: ", fill=default_colors["label"], font=font_label)
        y_offset += 30
        for item in data["team"][2].split(";"):
            card_draw.text((40, y_offset), f"• {item}", fill=default_colors["content"], font=font_content)
            y_offset += 28

    # 合成最终图片
    img.paste(card, (card_margin, card_margin))

    return _get_image_result(img)


def schedule_image(data: dict) -> BaseMessageComponent:
    """剑三活动日程图片生成"""
    # 配色方案保留原主题风格
    theme_colors = {
        "bg": "#F0F8FF",  # 背景
        "card_bg": "#FFFFFF",  # 卡片底色
        "border": "#87CEEB",  # 边框
        "highlight": "#FF69B4",  # 强调色
        "title": "#006FEE",  # 标题
        "subtitle": "#338EF7",  # 副标题
        "content": "#182C45",  # 正文
        "time_color": "#99C7FB"  # 时间
    }

    # 卡片布局参数
    card_width = 250
    card_height = 160
    card_margin = 15
    cards_per_row = 4
    max_rows = 3

    # 计算画布尺寸
    visible_items = data[:cards_per_row * max_rows]  # 限制最多显示12个
    rows = min(math.ceil(len(visible_items) / cards_per_row), max_rows)
    canvas_width = cards_per_row * card_width + (cards_per_row + 1) * card_margin
    canvas_height = rows * card_height + (rows + 1) * card_margin

    # 创建画布
    img = Image.new("RGB", (canvas_width, canvas_height), theme_colors["bg"])
    ImageDraw.Draw(img)

    # 字体配置（假设有支持中文的字体文件）
    font_title = _load_font(20)
    font_stage = _load_font(16)
    font_desc = _load_font(14)
    font_time = _load_font(13)

    # 生成卡片
    for index, event in enumerate(visible_items):
        row = index // cards_per_row
        col = index % cards_per_row
        x = card_margin + col * (card_width + card_margin)
        y = card_margin + row * (card_height + card_margin)

        # 创建卡片
        card = Image.new("RGB", (card_width, card_height), theme_colors["card_bg"])
        card_draw = ImageDraw.Draw(card)

        # 绘制边框
        card_draw.rounded_rectangle(
            [(0, 0), (card_width, card_height)],
            radius=10,
            outline=theme_colors["border"],
            width=2
        )

        # 地图名称（带图标）
        map_text = f"● {event['map']}-{event['site']}"
        card_draw.text((15, 10), map_text, fill=theme_colors["title"], font=font_title)

        # 时间标签
        time_width = font_time.getlength(event["time"])
        card_draw.rounded_rectangle(
            [(card_width - time_width - 25, 8), (card_width - 10, 32)],
            radius=6,
            fill=theme_colors["highlight"]
        )
        card_draw.text(
            (card_width - time_width - 15, 12),
            event["time"],
            fill="white",
            font=font_time
        )

        # 阶段信息
        card_draw.text(
            (15, 50),
            event["stage"],
            fill=theme_colors["highlight"],
            font=font_stage
        )

        # 任务描述（自动换行）
        desc_lines = []
        current_line = ""
        for word in event["desc"]:
            if font_desc.getlength(current_line + word) <= card_width - 30:
                current_line += word
            else:
                desc_lines.append(current_line)
                current_line = word
        desc_lines.append(current_line)

        for i, line in enumerate(desc_lines):
            y_pos = 85 + i * 20
            card_draw.text((15, y_pos), line, fill=theme_colors["content"], font=font_desc)

        # 合并到主画布
        img.paste(card, (x, y))

    return _get_image_result(img)
