# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/repo/platform_save_data/weibo/__init__.py
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
# @Time    : 2024/1/14 21:34
# @Desc    :

import re
from typing import List

import config
from model.m_weibo import WeiboNote, WeiboComment, WeiboCreator
from var import source_keyword_var

from .weibo_store_impl import *


class WeibostoreFactory:
    STORES = {
        "csv": WeiboCsvStoreImplement,
        "db": WeiboDbStoreImplement,
        "json": WeiboJsonStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = WeibostoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[WeibotoreFactory.create_store] Invalid save option only supported csv or db or json ..."
            )
        return store_class()


async def batch_update_weibo_notes(note_list: List[WeiboNote]):
    if not note_list:
        return
    for note_item in note_list:
        await update_weibo_note(note_item)


async def update_weibo_note(note_item: WeiboNote):
    utils.logger.info(
        f"[store.weibo.update_weibo_note] weibo note id:{note_item.note_id}, title:{note_item.content[:24]} ..."
    )

    save_content_item = note_item.model_dump()
    save_content_item["last_modify_ts"] = utils.get_current_timestamp()
    await WeibostoreFactory.create_store().store_content(content_item=save_content_item)


async def batch_update_weibo_note_comments(note_id: str, comments: List[WeiboComment]):
    if not comments:
        return
    for comment_item in comments:
        await update_weibo_note_comment(comment_item)


async def update_weibo_note_comment(comment_item: WeiboComment):
    utils.logger.info(
        f"[store.weibo.update_weibo_note_comment] Weibo note comment: {comment_item.comment_id}, content: {comment_item.content[:24]} ..."
    )

    save_comment_item = comment_item.model_dump(exclude={"sub_comments"})
    save_comment_item["last_modify_ts"] = utils.get_current_timestamp()
    await WeibostoreFactory.create_store().store_comment(comment_item=save_comment_item)


async def save_creator(creator_info: WeiboCreator):
    utils.logger.info(
        f"[store.weibo.save_creator] creator: user_id={creator_info.user_id}, nickname={creator_info.nickname}"
    )

    local_db_item = creator_info.model_dump()
    local_db_item["last_modify_ts"] = utils.get_current_timestamp()
    await WeibostoreFactory.create_store().store_creator(local_db_item)
