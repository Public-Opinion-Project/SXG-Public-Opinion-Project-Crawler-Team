# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/bilibili/field.py
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

"""
哔哩哔哩平台枚举字段定义模块

定义了在爬取哔哩哔哩数据时需要用到的各种枚举类型
包括搜索排序方式和评论排序方式等
"""

from enum import Enum


class SearchOrderType(Enum):
    """
    视频搜索排序类型枚举

    用于指定搜索结果的排序方式
    """
    # 综合排序（默认）
    DEFAULT = ""

    # 最多点击
    MOST_CLICK = "click"

    # 最新发布
    LAST_PUBLISH = "pubdate"

    # 最多弹幕（评论）
    MOST_DANMU = "dm"

    # 最多收藏
    MOST_MARK = "stow"


class CommentOrderType(Enum):
    """
    评论排序类型枚举

    用于指定评论列表的排序方式
    """
    # 按热度排序（只看按点赞排序的热门评论）
    DEFAULT = 0

    # 混合排序（热门评论 + 最新评论）
    MIXED = 1

    # 按时间排序（最新评论在前）
    TIME = 2
