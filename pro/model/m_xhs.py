# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/model/m_xhs.py
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


# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class NoteUrlInfo(BaseModel):
    note_id: str = Field(title="note id")
    xsec_token: str = Field(title="xsec token")
    xsec_source: str = Field(title="xsec source")


class CreatorUrlInfo(BaseModel):
    creator_id: str = Field(title="creator id")
    xsec_token: str = Field(title="xsec token")
    xsec_source: str = Field(title="xsec source")


class XhsNote(BaseModel):
    """
    小红书笔记
    """

    note_id: str = Field(default="", description="笔记ID")
    type: str = Field(default="", description="笔记类型(normal | video)")
    title: str = Field(default="", description="笔记标题")
    desc: str = Field(default="", description="笔记描述")
    video_url: str = Field(default="", description="视频链接")
    time: str = Field(default="", description="发布时间戳")
    last_update_time: str = Field(default="", description="最后更新时间戳")
    ip_location: str = Field(default="", description="IP地理位置")
    image_list: str = Field(default="", description="图片链接列表，逗号分隔")
    tag_list: str = Field(default="", description="标签列表，逗号分隔")
    note_url: str = Field(default="", description="笔记链接")
    source_keyword: str = Field(default="", description="来源关键词")

    liked_count: str = Field(default="", description="点赞数")
    collected_count: str = Field(default="", description="收藏数")
    comment_count: str = Field(default="", description="评论数")
    share_count: str = Field(default="", description="分享数")

    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像")


class XhsComment(BaseModel):
    """
    小红书评论
    """

    comment_id: str = Field(default="", description="评论ID")
    parent_comment_id: str = Field(default="", description="父评论ID")
    target_comment_id: str = Field(default="", description="目标评论ID（回复某条评论）")
    note_id: str = Field(default="", description="笔记ID")
    content: str = Field(default="", description="评论内容")
    create_time: str = Field(default="", description="创建时间戳")
    ip_location: str = Field(default="", description="IP地理位置")
    sub_comment_count: str = Field(default="0", description="子评论数")
    like_count: str = Field(default="", description="点赞数")
    pictures: str = Field(default="", description="图片链接列表，逗号分隔")
    note_url: str = Field(default="", description="笔记链接")

    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像")


class XhsCreator(BaseModel):
    """
    小红书创作者
    """

    user_id: str = Field(default="", description="用户ID")
    nickname: str = Field(default="", description="用户昵称")
    avatar: str = Field(default="", description="用户头像")
    gender: str = Field(default="", description="性别")
    desc: str = Field(default="", description="个人简介")
    ip_location: str = Field(default="", description="IP地理位置")
    follows: str = Field(default="", description="关注数")
    fans: str = Field(default="", description="粉丝数")
    interaction: str = Field(default="", description="互动数")
    tag_list: str = Field(default="", description="标签列表，JSON字符串")
