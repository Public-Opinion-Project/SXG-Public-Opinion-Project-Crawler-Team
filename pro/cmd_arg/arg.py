# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/cmd_arg/arg.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
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

import sys
from typing import Optional
from enum import Enum

import typer
from typing_extensions import Annotated

import config
import constant


class PlatformEnum(str, Enum):
    """支持的媒体平台枚举"""
    XHS = constant.XHS_PLATFORM_NAME
    DOUYIN = constant.DOUYIN_PLATFORM_NAME
    KUAISHOU = constant.KUAISHOU_PLATFORM_NAME
    WEIBO = constant.WEIBO_PLATFORM_NAME
    BILIBILI = constant.BILIBILI_PLATFORM_NAME
    TIEBA = constant.TIEBA_PLATFORM_NAME
    ZHIHU = constant.ZHIHU_PLATFORM_NAME


class CrawlerTypeEnum(str, Enum):
    """爬虫类型枚举"""
    SEARCH = constant.CRALER_TYPE_SEARCH
    DETAIL = constant.CRALER_TYPE_DETAIL
    CREATOR = constant.CRALER_TYPE_CREATOR
    HOMEFEED = constant.CRALER_TYPE_HOMEFEED


class SaveDataOptionEnum(str, Enum):
    """数据保存选项枚举"""
    CSV = "csv"
    DB = "db"
    JSON = "json"


def parse_cmd():
    """
    解析命令行参数并更新配置

    这个函数保持与原有 argparse 版本的完全兼容性，
    同时提供更好的用户体验和错误处理。
    """
    def main(
        platform: Annotated[
            PlatformEnum,
            typer.Option(
                "--platform",
                help="🎯 选择媒体平台 (xhs=小红书, dy=抖音, ks=快手, bili=B站, wb=微博, tieba=贴吧, zhihu=知乎)"
            )
        ] = PlatformEnum.XHS,

        crawler_type: Annotated[
            CrawlerTypeEnum,
            typer.Option(
                "--type",
                help="🔍 爬虫类型 (search=关键词搜索, detail=帖子详情, creator=创作者主页, homefeed=首页推荐)"
            )
        ] = CrawlerTypeEnum.SEARCH,

        enable_checkpoint: Annotated[
            bool,
            typer.Option(
                "--enable_checkpoint/--no-enable_checkpoint",
                help="💾 是否启用断点续爬功能"
            )
        ] = config.ENABLE_CHECKPOINT,

        checkpoint_id: Annotated[
            str,
            typer.Option(
                "--checkpoint_id",
                help="🔖 指定断点续爬的检查点ID，如果为空则加载最新的检查点"
            )
        ] = config.SPECIFIED_CHECKPOINT_ID,

        keywords: Annotated[
            str,
            typer.Option(
                "--keywords",
                help="🔤 搜索关键词，多个关键词用逗号分隔"
            )
        ] = config.KEYWORDS,

    ):
        """
        🚀 MediaCrawlerPro - 多平台媒体爬虫工具

        支持小红书、抖音、快手、B站、微博、贴吧、知乎等平台的数据爬取。

        [bold green]示例用法:[/bold green]

        • 爬取小红书搜索结果：
          python main.py --platform xhs --type search --keywords "深度学习,AI"

        • 启用断点续爬：
          python main.py --platform dy --type creator --enable_checkpoint

        • 禁用断点续爬：
          python main.py --platform wb --type detail --no-enable_checkpoint

        """
        # 更新全局配置，保持与原有逻辑的兼容性
        config.PLATFORM = platform.value
        config.CRAWLER_TYPE = crawler_type.value
        config.KEYWORDS = keywords
        config.ENABLE_CHECKPOINT = enable_checkpoint
        config.SPECIFIED_CHECKPOINT_ID = checkpoint_id


    # 检查是否是帮助命令
    import sys
    if '--help' in sys.argv or '-h' in sys.argv:
        # 如果是帮助命令，直接运行 typer 并退出
        typer.run(main)
        return

    # 使用 typer.run 但捕获 SystemExit 以避免程序提前退出
    try:
        typer.run(main)
    except SystemExit as e:
        # 如果是参数错误导致的退出，重新抛出
        if e.code != 0:
            raise
        # 如果是正常的参数解析完成，继续执行后续代码
        pass
