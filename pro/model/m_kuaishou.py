# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/model/m_kuaishou.py
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


from pydantic import BaseModel, Field


class KuaishouVideo(BaseModel):
    """
    快手视频
    """

    video_id: str = Field(default="", description="视频ID")
    video_type: str = Field(default="", description="视频类型")
    title: str = Field(default="", description="视频标题")
    desc: str = Field(default="", description="视频描述")
    create_time: str = Field(default="", description="创建时间戳")
    liked_count: str = Field(default="", description="点赞数")
    viewd_count: str = Field(default="", description="观看数")
    video_url: str = Field(default="", description="视频详情页URL")
    video_cover_url: str = Field(default="", description="视频封面图URL")
    video_play_url: str = Field(default="", description="视频播放URL")
    source_keyword: str = Field(default="", description="搜索来源关键字")

    # 用户信息
    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像地址")


class KuaishouVideoComment(BaseModel):
    """
    快手视频评论
    """

    comment_id: str = Field(default="", description="评论ID")
    parent_comment_id: str = Field(default="", description="父评论ID")
    video_id: str = Field(default="", description="视频ID")
    content: str = Field(default="", description="评论内容")
    create_time: str = Field(default="", description="评论时间戳")
    sub_comment_count: str = Field(default="", description="子评论数")
    like_count: str = Field(default="", description="点赞数")

    # 用户信息
    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像地址")


class KuaishouCreator(BaseModel):
    """
    快手创作者
    """

    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像地址")
    gender: str = Field(default="", description="性别")
    desc: str = Field(default="", description="个人简介")
    ip_location: str = Field(default="", description="IP地理位置")
    follows: str = Field(default="", description="关注数")
    fans: str = Field(default="", description="粉丝数")
    videos_count: str = Field(default="", description="作品数")
