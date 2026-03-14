# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/cmd_arg/arg.py
# GitHub：https://github.com/NanmiCoder
# 基于 NON-COMMERCIAL LEARNING LICENSE 1.1 许可证授权
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


from __future__ import annotations


import sys
from enum import Enum
from types import SimpleNamespace
from typing import Iterable, Optional, Sequence, Type, TypeVar

import typer
from typing_extensions import Annotated

import config
from tools.utils import str2bool


# 类型变量，用于泛型枚举类型
# TypeVar for generic enum types
EnumT = TypeVar("EnumT", bound=Enum)


class PlatformEnum(str, Enum):
    """
    支持的媒体平台枚举
    定义了爬虫支持的所有社交媒体平台
    """
    # 小红书
    XHS = "xhs"
    # 抖音
    DOUYIN = "dy"
    # 快手
    KUAISHOU = "ks"
    # 哔哩哔哩
    BILIBILI = "bili"
    # 微博
    WEIBO = "wb"
    # 百度贴吧
    TIEBA = "tieba"
    # 知乎
    ZHIHU = "zhihu"


class LoginTypeEnum(str, Enum):
    """
    登录类型枚举
    定义了爬虫支持的登录方式
    """
    # 二维码登录
    QRCODE = "qrcode"
    # 手机号登录
    PHONE = "phone"
    # Cookie登录
    COOKIE = "cookie"


class CrawlerTypeEnum(str, Enum):
    """
    爬虫类型枚举
    定义了爬虫的不同运行模式
    """
    # 搜索模式：根据关键词搜索内容
    SEARCH = "search"
    # 详情模式：获取指定帖子/视频的详细信息
    DETAIL = "detail"
    # 创作者模式：获取指定创作者发布的内容
    CREATOR = "creator"


class SaveDataOptionEnum(str, Enum):
    """
    数据保存选项枚举
    定义了爬取数据可以保存的形式
    """
    # CSV文件
    CSV = "csv"
    # MySQL数据库
    DB = "db"
    # JSON文件
    JSON = "json"
    # JSONL文件（每行一个JSON对象）
    JSONL = "jsonl"
    # SQLite数据库
    SQLITE = "sqlite"
    # MongoDB数据库
    MONGODB = "mongodb"
    # Excel文件
    EXCEL = "excel"
    # PostgreSQL数据库
    POSTGRES = "postgres"


class InitDbOptionEnum(str, Enum):
    """
    数据库初始化选项
    定义了可以初始化的数据库类型
    """
    # SQLite数据库
    SQLITE = "sqlite"
    # MySQL数据库
    MYSQL = "mysql"
    # PostgreSQL数据库
    POSTGRES = "postgres"


def _to_bool(value: bool | str) -> bool:
    """
    将值转换为布尔类型

    参数:
        value: 布尔值或字符串形式的布尔值

    返回:
        转换后的布尔值

    说明:
        如果输入已经是布尔类型，直接返回
        否则调用 str2bool 工具函数进行转换
    """
    if isinstance(value, bool):
        return value
    return str2bool(value)


def _coerce_enum(
    enum_cls: Type[EnumT],
    value: EnumT | str,
    default: EnumT,
) -> EnumT:
    """
    安全地将原始配置值转换为枚举成员

    参数:
        enum_cls: 枚举类类型
        value: 需要转换的值（枚举成员或字符串）
        default: 转换失败时使用的默认值

    返回:
        转换后的枚举成员

    说明:
        如果值已经是正确的枚举类型，直接返回
        尝试将字符串转换为枚举成员
        如果转换失败，打印警告并返回默认值
    """
    # 如果值已经是枚举类型，直接返回
    if isinstance(value, enum_cls):
        return value

    try:
        # 尝试将字符串值转换为枚举成员
        return enum_cls(value)
    except ValueError:
        # 转换失败时，显示警告并返回默认值
        typer.secho(
            f"⚠️ 配置值 '{value}' 不在 {enum_cls.__name__} 支持的范围内，将回退到默认值 '{default.value}'。",
            fg=typer.colors.YELLOW,
        )
        return default


def _normalize_argv(argv: Optional[Sequence[str]]) -> Iterable[str]:
    """
    规范化命令行参数

    参数:
        argv: 命令行参数列表，None 表示使用 sys.argv[1:]

    返回:
        规范化的命令行参数列表
    """
    if argv is None:
        # 如果未提供参数，使用系统默认的命令行参数
        return list(sys.argv[1:])
    return list(argv)


def _inject_init_db_default(args: Sequence[str]) -> list[str]:
    """
    确保裸 --init_db 参数默认为 sqlite 以保持向后兼容性

    参数:
        args: 命令行参数列表

    返回:
        处理后的命令行参数列表

    说明:
        如果用户只写了 --init_db 而没有指定值
        自动补充默认值 sqlite
    """
    normalized: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        normalized.append(arg)

        # 检测到 --init_db 参数
        if arg == "--init_db":
            # 获取下一个参数
            next_arg = args[i + 1] if i + 1 < len(args) else None
            # 如果下一个参数不存在或是以 - 开头的选项，则添加默认值
            if not next_arg or next_arg.startswith("-"):
                normalized.append(InitDbOptionEnum.SQLITE.value)
        i += 1

    return normalized


async def parse_cmd(argv: Optional[Sequence[str]] = None):
    """
    使用 Typer 解析命令行参数

    参数:
        argv: 命令行参数列表，None 表示使用 sys.argv

    返回:
        SimpleNamespace 对象，包含所有解析后的配置参数

    说明:
        这是整个爬虫的入口点
        定义了所有可用的命令行选项及其默认值
        使用 Typer 库实现 CLI 参数解析
    """
    # 创建 Typer 应用实例
    app = typer.Typer(add_completion=False)

    @app.callback(invoke_without_command=True)
    def main(
        # ==================== 基础配置 ====================
        platform: Annotated[
            PlatformEnum,
            typer.Option(
                "--platform",
                help="媒体平台选择 (xhs=小红书 | dy=抖音 | ks=快手 | bili=哔哩哔哩 | wb=微博 | tieba=百度贴吧 | zhihu=知乎)",
                rich_help_panel="基础配置",
            ),
        ] = _coerce_enum(PlatformEnum, config.PLATFORM, PlatformEnum.XHS),

        # ==================== 账号配置 ====================
        lt: Annotated[
            LoginTypeEnum,
            typer.Option(
                "--lt",
                help="登录方式 (qrcode=二维码 | phone=手机号 | cookie=Cookie)",
                rich_help_panel="账号配置",
            ),
        ] = _coerce_enum(LoginTypeEnum, config.LOGIN_TYPE, LoginTypeEnum.QRCODE),

        # ==================== 爬虫类型配置 ====================
        crawler_type: Annotated[
            CrawlerTypeEnum,
            typer.Option(
                "--type",
                help="爬虫类型 (search=搜索 | detail=详情 | creator=创作者)",
                rich_help_panel="基础配置",
            ),
        ] = _coerce_enum(CrawlerTypeEnum, config.CRAWLER_TYPE, CrawlerTypeEnum.SEARCH),

        # 起始页码
        start: Annotated[
            int,
            typer.Option(
                "--start",
                help="起始页码",
                rich_help_panel="基础配置",
            ),
        ] = config.START_PAGE,

        # 搜索关键词
        keywords: Annotated[
            str,
            typer.Option(
                "--keywords",
                help="输入关键词，多个关键词用逗号分隔",
                rich_help_panel="基础配置",
            ),
        ] = config.KEYWORDS,

        # ==================== 评论配置 ====================
        # 是否爬取一级评论
        get_comment: Annotated[
            str,
            typer.Option(
                "--get_comment",
                help="是否爬取一级评论，支持 yes/true/t/y/1 或 no/false/f/n/0",
                rich_help_panel="评论配置",
                show_default=True,
            ),
        ] = str(config.ENABLE_GET_COMMENTS),

        # 是否爬取二级评论（回复）
        get_sub_comment: Annotated[
            str,
            typer.Option(
                "--get_sub_comment",
                help="是否爬取二级评论，支持 yes/true/t/y/1 或 no/false/f/n/0",
                rich_help_panel="评论配置",
                show_default=True,
            ),
        ] = str(config.ENABLE_GET_SUB_COMMENTS),

        # 每个帖子/视频最多爬取的一级评论数量
        max_comments_count_singlenotes: Annotated[
            int,
            typer.Option(
                "--max_comments_count_singlenotes",
                help="每个帖子/视频最多爬取的一级评论数量",
                rich_help_panel="评论配置",
            ),
        ] = config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,

        # ==================== 运行时配置 ====================
        # 是否使用无头模式（不显示浏览器界面）
        headless: Annotated[
            str,
            typer.Option(
                "--headless",
                help="是否启用无头模式（适用于 Playwright 和 CDP），支持 yes/true/t/y/1 或 no/false/f/n/0",
                rich_help_panel="运行时配置",
                show_default=True,
            ),
        ] = str(config.HEADLESS),

        # ==================== 存储配置 ====================
        # 数据保存方式
        save_data_option: Annotated[
            SaveDataOptionEnum,
            typer.Option(
                "--save_data_option",
                help="数据保存方式 (csv=CSV文件 | db=MySQL数据库 | json=JSON文件 | jsonl=JSONL文件 | sqlite=SQLite数据库 | mongodb=MongoDB数据库 | excel=Excel文件 | postgres=PostgreSQL数据库)",
                rich_help_panel="存储配置",
            ),
        ] = _coerce_enum(
            SaveDataOptionEnum, config.SAVE_DATA_OPTION, SaveDataOptionEnum.JSONL
        ),

        # 初始化数据库表结构
        init_db: Annotated[
            Optional[InitDbOptionEnum],
            typer.Option(
                "--init_db",
                help="初始化数据库表结构 (sqlite | mysql | postgres)",
                rich_help_panel="存储配置",
            ),
        ] = None,

        # 数据保存路径
        save_data_path: Annotated[
            str,
            typer.Option(
                "--save_data_path",
                help="数据保存路径，默认为空将保存到data文件夹",
                rich_help_panel="存储配置",
            ),
        ] = config.SAVE_DATA_PATH,

        # ==================== 账号配置 ====================
        # Cookie登录时使用的Cookie值
        cookies: Annotated[
            str,
            typer.Option(
                "--cookies",
                help="Cookie登录方式使用的Cookie值",
                rich_help_panel="账号配置",
            ),
        ] = config.COOKIES,

        # ==================== 基础配置（详情/创作者模式用） ====================
        # 详情模式：指定要爬取的帖子/视频ID
        specified_id: Annotated[
            str,
            typer.Option(
                "--specified_id",
                help="详情模式下的帖子/视频ID列表，多个ID用逗号分隔（支持完整URL或ID）",
                rich_help_panel="基础配置",
            ),
        ] = "",

        # 创作者模式：指定要爬取的创作者ID
        creator_id: Annotated[
            str,
            typer.Option(
                "--creator_id",
                help="创作者模式下的创作者ID列表，多个ID用逗号分隔（支持完整URL或ID）",
                rich_help_panel="基础配置",
            ),
        ] = "",

        # ==================== 性能配置 ====================
        # 最大并发爬虫数量
        max_concurrency_num: Annotated[
            int,
            typer.Option(
                "--max_concurrency_num",
                help="最大并发爬虫数量",
                rich_help_panel="性能配置",
            ),
        ] = config.MAX_CONCURRENCY_NUM,

        # ==================== 代理配置 ====================
        # 是否启用IP代理
        enable_ip_proxy: Annotated[
            str,
            typer.Option(
                "--enable_ip_proxy",
                help="是否启用IP代理，支持 yes/true/t/y/1 或 no/false/f/n/0",
                rich_help_panel="代理配置",
                show_default=True,
            ),
        ] = str(config.ENABLE_IP_PROXY),

        # IP代理池数量
        ip_proxy_pool_count: Annotated[
            int,
            typer.Option(
                "--ip_proxy_pool_count",
                help="IP代理池数量",
                rich_help_panel="代理配置",
            ),
        ] = config.IP_PROXY_POOL_COUNT,

        # IP代理提供商名称
        ip_proxy_provider_name: Annotated[
            str,
            typer.Option(
                "--ip_proxy_provider_name",
                help="IP代理提供商名称 (kuaidaili | wandouhttp)",
                rich_help_panel="代理配置",
            ),
        ] = config.IP_PROXY_PROVIDER_NAME,
    ) -> SimpleNamespace:
        """MediaCrawler 命令行入口"""

        # ==================== 参数类型转换 ====================
        # 将字符串类型的参数转换为布尔值
        enable_comment = _to_bool(get_comment)
        enable_sub_comment = _to_bool(get_sub_comment)
        enable_headless = _to_bool(headless)
        enable_ip_proxy_value = _to_bool(enable_ip_proxy)
        # 处理可选的初始化数据库参数
        init_db_value = init_db.value if init_db else None

        # ==================== 解析ID列表 ====================
        # 将指定ID和创作者ID字符串拆分为列表
        # specified_id_list: 详情模式下的帖子/视频ID列表
        # creator_id_list: 创作者模式下的创作者ID列表
        specified_id_list = [id.strip() for id in specified_id.split(",") if id.strip()] if specified_id else []
        creator_id_list = [id.strip() for id in creator_id.split(",") if id.strip()] if creator_id else []

        # ==================== 更新全局配置 ====================
        # 将解析后的命令行参数更新到全局配置对象中
        config.PLATFORM = platform.value
        config.LOGIN_TYPE = lt.value
        config.CRAWLER_TYPE = crawler_type.value
        config.START_PAGE = start
        config.KEYWORDS = keywords
        config.ENABLE_GET_COMMENTS = enable_comment
        config.ENABLE_GET_SUB_COMMENTS = enable_sub_comment
        config.HEADLESS = enable_headless
        config.CDP_HEADLESS = enable_headless  # CDP也使用同样的无头模式设置
        config.SAVE_DATA_OPTION = save_data_option.value
        config.COOKIES = cookies
        config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = max_comments_count_singlenotes
        config.MAX_CONCURRENCY_NUM = max_concurrency_num
        config.SAVE_DATA_PATH = save_data_path
        config.ENABLE_IP_PROXY = enable_ip_proxy_value
        config.IP_PROXY_POOL_COUNT = ip_proxy_pool_count
        config.IP_PROXY_PROVIDER_NAME = ip_proxy_provider_name

        # ==================== 设置平台特定的ID列表 ====================
        # 根据不同的平台，将指定的ID列表设置到对应的配置项中

        # 处理详情模式的指定ID
        if specified_id_list:
            if platform == PlatformEnum.XHS:
                # 小红书指定的笔记URL列表
                config.XHS_SPECIFIED_NOTE_URL_LIST = specified_id_list
            elif platform == PlatformEnum.BILIBILI:
                # 哔哩哔哩指定的视频ID列表
                config.BILI_SPECIFIED_ID_LIST = specified_id_list
            elif platform == PlatformEnum.DOUYIN:
                # 抖音指定的视频ID列表
                config.DY_SPECIFIED_ID_LIST = specified_id_list
            elif platform == PlatformEnum.WEIBO:
                # 微博指定的帖子ID列表
                config.WEIBO_SPECIFIED_ID_LIST = specified_id_list
            elif platform == PlatformEnum.KUAISHOU:
                # 快手指定的视频ID列表
                config.KS_SPECIFIED_ID_LIST = specified_id_list

        # 处理创作者模式的创作者ID
        if creator_id_list:
            if platform == PlatformEnum.XHS:
                # 小红书创作者ID列表
                config.XHS_CREATOR_ID_LIST = creator_id_list
            elif platform == PlatformEnum.BILIBILI:
                # 哔哩哔哩创作者ID列表
                config.BILI_CREATOR_ID_LIST = creator_id_list
            elif platform == PlatformEnum.DOUYIN:
                # 抖音创作者ID列表
                config.DY_CREATOR_ID_LIST = creator_id_list
            elif platform == PlatformEnum.WEIBO:
                # 微博创作者ID列表
                config.WEIBO_CREATOR_ID_LIST = creator_id_list
            elif platform == PlatformEnum.KUAISHOU:
                # 快手创作者ID列表
                config.KS_CREATOR_ID_LIST = creator_id_list

        # ==================== 返回解析结果 ====================
        # 将所有配置封装到 SimpleNamespace 对象中返回
        return SimpleNamespace(
            platform=config.PLATFORM,
            lt=config.LOGIN_TYPE,
            type=config.CRAWLER_TYPE,
            start=config.START_PAGE,
            keywords=config.KEYWORDS,
            get_comment=config.ENABLE_GET_COMMENTS,
            get_sub_comment=config.ENABLE_GET_SUB_COMMENTS,
            headless=config.HEADLESS,
            save_data_option=config.SAVE_DATA_OPTION,
            init_db=init_db_value,
            cookies=config.COOKIES,
            specified_id=specified_id,
            creator_id=creator_id,
        )

    # 获取 Typer 命令对象
    command = typer.main.get_command(app)

    # ==================== 解析命令行参数 ====================
    # 规范化命令行参数
    cli_args = _normalize_argv(argv)
    # 为裸 --init_db 参数注入默认值
    cli_args = _inject_init_db_default(cli_args)

    # ==================== 执行命令 ====================
    try:
        # 执行命令行解析
        result = command.main(args=cli_args, standalone_mode=False)
        # 如果返回的是整数（退出码），抛出系统退出异常
        if isinstance(result, int):
            raise SystemExit(result)
        return result
    except typer.Exit as exc:
        # 处理 Typer 退出异常
        raise SystemExit(exc.exit_code) from exc
