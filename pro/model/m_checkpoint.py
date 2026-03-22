# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/model/m_checkpoint.py
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

from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class CheckpointNote(BaseModel):
    note_id: str = Field(..., description="帖子ID")
    extra_params_info: Optional[Dict[str, Any]] = Field(
        None, description="额外参数信息"
    )
    is_success_crawled: bool = Field(False, description="是否成功爬取")
    is_success_crawled_comments: bool = Field(False, description="是否成功爬取评论")
    current_note_comment_cursor: Optional[str] = Field(
        "", description="当前帖子评论游标"
    )


class Checkpoint(BaseModel):
    """
    检查点
    """

    # 主键
    id: Optional[str] = Field(None, description="检查点ID")

    # 基础字段
    platform: str = Field(
        ..., description="平台名称，如 xhs、dy、ks、bili、wb、tieba、zhihu"
    )
    mode: str = Field(..., description="模式：search/detail/creator/homefeed")

    # 搜索模式相关字段
    current_search_keyword: Optional[str] = Field(None, description="当前搜索关键词")
    current_search_page: Optional[int] = Field(None, description="当前搜索页码")
    current_search_id: Optional[str] = Field(None, description="当前搜索ID")

    # 创作者模式相关字段
    current_creator_id: Optional[str] = Field(None, description="当前创作者ID")
    current_creator_page: Optional[str] = Field(None, description="当前创作者页码")

    # 首页推荐流相关字段
    current_homefeed_cursor: Optional[str] = Field(
        None, description="当前首页推荐流游标"
    )
    current_homefeed_note_index: Optional[int] = Field(
        None, description="当前首页推荐流笔记索引"
    )

    # 帖子相关字段（搜索模式、详情模式、创作者模式、首页推荐流能用到）
    crawled_note_list: Optional[List[CheckpointNote]] = Field(
        [], description="已爬取的帖子列表"
    )
