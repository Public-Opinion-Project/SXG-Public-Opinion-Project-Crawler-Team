# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/repo/platform_save_data/xhs/__init__.py
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
# @Author  : relakkes@gmail.com
# @Time    : 2024/1/14 17:34
# @Desc    :
import json
from typing import Dict, List

import config
from base.base_crawler import AbstractStore
from model.m_xhs import XhsComment, XhsCreator, XhsNote
from pkg.tools import utils
from repo.platform_save_data.xhs.xhs_store_impl import (
    XhsCsvStoreImplement,
    XhsDbStoreImplement,
    XhsJsonStoreImplement,
)
from var import source_keyword_var


class XhsStoreFactory:
    STORES = {
        "csv": XhsCsvStoreImplement,
        "db": XhsDbStoreImplement,
        "json": XhsJsonStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = XhsStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[XhsStoreFactory.create_store] Invalid save option only supported csv or db or json ..."
            )
        return store_class()


async def batch_update_xhs_notes(notes: List[XhsNote]):
    """
    批量更新小红书笔记
    Args:
        notes: 笔记列表
    """
    if not notes:
        return

    for note_item in notes:
        await update_xhs_note(note_item)


async def update_xhs_note(note_item: XhsNote):
    """
    更新小红书笔记
    Args:
        note_item: 笔记对象
    """
    note_item.source_keyword = source_keyword_var.get()
    local_db_item = note_item.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})

    print_title = note_item.title[:30] or note_item.desc[:30]
    utils.logger.info(
        f"[store.xhs.update_xhs_note] xhs note, id: {note_item.note_id}, title: {print_title}"
    )
    await XhsStoreFactory.create_store().store_content(local_db_item)


async def batch_update_xhs_note_comments(comments: List[XhsComment]):
    """
    批量更新小红书笔记评论
    Args:
        comments: 评论列表
    """
    if not comments:
        return

    for comment_item in comments:
        await update_xhs_note_comment(comment_item)


async def update_xhs_note_comment(comment_item: XhsComment):
    """
    更新小红书笔记评论
    Args:
        comment_item: 评论对象
    """
    local_db_item = comment_item.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})

    utils.logger.info(
        f"[store.xhs.update_xhs_note_comment] xhs note comment, note_id: {comment_item.note_id}, comment_id: {comment_item.comment_id}"
    )
    await XhsStoreFactory.create_store().store_comment(local_db_item)


async def save_creator(creator: XhsCreator):
    """
    保存小红书创作者信息
    Args:
        creator: 创作者对象
    """
    if not creator:
        return

    local_db_item = creator.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})

    utils.logger.info(
        f"[store.xhs.save_creator] creator: {creator.user_id} - {creator.nickname}"
    )
    await XhsStoreFactory.create_store().store_creator(local_db_item)
