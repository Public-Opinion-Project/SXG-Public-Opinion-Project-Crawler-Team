# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/bilibili/exception.py
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
哔哩哔哩平台自定义异常模块

定义了在爬取哔哩哔哩数据时可能遇到的特定异常类型
"""

from httpx import RequestError


class DataFetchError(RequestError):
    """
    数据获取错误

    当从哔哩哔哩 API 获取数据时发生错误
    可能的原因包括：网络请求失败、JSON 解析失败、API 返回错误等
    """


class IPBlockError(RequestError):
    """
    IP 被封禁错误

    当请求频率过快导致服务器封禁 IP 时抛出此异常
    建议降低请求频率或使用代理 IP
    """
