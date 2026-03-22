# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/model/m_bilibili.py
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

from typing import Optional

from pydantic import BaseModel, Field


class BilibiliVideo(BaseModel):
    """B站视频模型"""

    # 视频基本信息
    video_id: str = Field(default="", description="视频ID (aid)")
    bvid: str = Field(default="", description="视频ID (bvid)")
    video_type: str = Field(default="", description="视频类型")
    title: str = Field(default="", description="视频标题")
    desc: str = Field(default="", description="视频描述")
    create_time: str = Field(default="", description="视频发布时间戳")
    duration: str = Field(default="", description="视频时长")

    # 视频统计信息
    liked_count: str = Field(default="", description="视频点赞数")
    video_play_count: str = Field(default="", description="视频播放数量")
    video_danmaku: str = Field(default="", description="视频弹幕数量")
    video_comment: str = Field(default="", description="视频评论数量")

    # 视频链接
    video_url: str = Field(default="", description="视频详情URL")
    video_cover_url: str = Field(default="", description="视频封面图URL")

    # 作者信息
    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像地址")

    # 其他信息
    source_keyword: str = Field(default="", description="搜索来源关键字")

    # 时间戳字段（仅在写入数据库时使用）
    add_ts: Optional[int] = Field(default=None, description="记录添加时间戳")
    last_modify_ts: Optional[int] = Field(default=None, description="记录最后修改时间戳")


class BilibiliComment(BaseModel):
    """B站视频评论模型"""

    # 评论基本信息
    comment_id: str = Field(default="", description="评论ID")
    video_id: str = Field(default="", description="视频ID")
    content: str = Field(default="", description="评论内容")
    create_time: str = Field(default="", description="评论时间戳")

    # 评论统计信息
    sub_comment_count: str = Field(default="", description="评论回复数")
    like_count: str = Field(default="0", description="点赞数")

    # 评论关系
    parent_comment_id: str = Field(default="", description="父评论ID")

    # 用户信息
    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像地址")

    # 时间戳字段（仅在写入数据库时使用）
    add_ts: Optional[int] = Field(default=None, description="记录添加时间戳")
    last_modify_ts: Optional[int] = Field(default=None, description="记录最后修改时间戳")


class BilibiliUpInfo(BaseModel):
    """B站UP主信息模型"""

    # UP主基本信息
    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像地址")
    description: str = Field(default="", description="用户描述")

    # UP主统计信息
    follower_count: str = Field(default="", description="粉丝数")
    following_count: str = Field(default="", description="关注数")
    content_count: str = Field(default="", description="作品数")

    # 时间戳字段（仅在写入数据库时使用）
    add_ts: Optional[int] = Field(default=None, description="记录添加时间戳")
    last_modify_ts: Optional[int] = Field(default=None, description="记录最后修改时间戳")


# 保留原有的模型以确保兼容性
class CreatorQueryResponse(BaseModel):
    """
    查询创作者主页响应
    """
    nickname: str = Field(..., title="昵称", description="昵称")
    avatar: str = Field(default="", title="头像", description="头像")
    description: str = Field(default="", title="描述", description="描述")
    user_id: str = Field(default="", title="用户ID", description="用户ID")
    follower_count: str = Field(default="", title="粉丝数", description="粉丝数")
    following_count: str = Field(default="", title="关注数", description="关注数")
    content_count: str = Field(default="", title="作品数", description="作品数")


class VideoIdInfo(BaseModel):
    """
    批量获取视频评论的请求参数
    """
    aid: str = Field(..., title="B站的视频ID,用户不可见的，通常在一些列表接口中返回的，爬取评论需要这个ID")
    bvid: str = Field(..., title="B站的视频ID，用户可见的")
