# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/douyin/field.py
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


"""
抖音字段枚举模块

定义抖音搜索和筛选相关的枚举类型
包括搜索频道、排序方式、发布时间等
"""

from enum import Enum


class SearchChannelType(Enum):
    """
    搜索频道类型
    
    用于指定搜索结果的类型
    """
    GENERAL = "aweme_general"  # 综合
    VIDEO = "aweme_video_web"  # 视频
    USER = "aweme_user_web"    # 用户
    LIVE = "aweme_live"        # 直播


class SearchSortType(Enum):
    """
    搜索排序类型
    
    用于指定搜索结果的排序方式
    """
    GENERAL = 0   # 综合排序
    MOST_LIKE = 1 # 最多点赞
    LATEST = 2    # 最新发布

class PublishTimeType(Enum):
    """
    发布时间类型
    
    用于筛选指定时间范围内发布的视频
    """
    UNLIMITED = 0   # 不限
    ONE_DAY = 1     # 一天内
    ONE_WEEK = 7    # 一周内
    SIX_MONTH = 180 # 半年内
