# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/store/bilibili/_store_impl.py
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
# @Author  : persist1@126.com
# @Time    : 2025/9/5 19:34
# @Desc    : Bilibili存储实现类
import asyncio
import csv
import json
import os
import pathlib
from typing import Dict

import aiofiles
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import config
from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import BilibiliVideoComment, BilibiliVideo, BilibiliUpInfo, BilibiliUpDynamic, BilibiliContactInfo
from tools.async_file_writer import AsyncFileWriter
from tools import utils, words
from var import crawler_type_var
from database.mongodb_store_base import MongoDBStoreBase


class BiliCsvStoreImplement(AbstractStore):
    def __init__(self):
        self.file_writer = AsyncFileWriter(
            crawler_type=crawler_type_var.get(),
            platform="bili"
        )

    async def store_content(self, content_item: Dict):
        """
        内容CSV存储实现
        Args:
            content_item:

        Returns:

        """
        await self.file_writer.write_to_csv(
            item=content_item,
            item_type="videos"
        )

    async def store_comment(self, comment_item: Dict):
        """
        评论CSV存储实现
        Args:
            comment_item:

        Returns:

        """
        await self.file_writer.write_to_csv(
            item=comment_item,
            item_type="comments"
        )

    async def store_creator(self, creator: Dict):
        """
        创作者CSV存储实现
        Args:
            creator:

        Returns:

        """
        await self.file_writer.write_to_csv(
            item=creator,
            item_type="creators"
        )

    async def store_contact(self, contact_item: Dict):
        """
        创作者联系人CSV存储实现
        Args:
            contact_item: 创作者的联系人项字典

        Returns:

        """
        await self.file_writer.write_to_csv(
            item=contact_item,
            item_type="contacts"
        )

    async def store_dynamic(self, dynamic_item: Dict):
        """
        创作者动态CSV存储实现
        Args:
            dynamic_item: 创作者的动态项字典

        Returns:

        """
        await self.file_writer.write_to_csv(
            item=dynamic_item,
            item_type="dynamics"
        )


class BiliDbStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        """
        Bilibili内容数据库存储实现
        Args:
            content_item: 内容项字典
        """
        video_id = int(content_item.get("video_id"))
        content_item["video_id"] = video_id
        content_item["user_id"] = int(content_item.get("user_id", 0) or 0)
        content_item["liked_count"] = int(content_item.get("liked_count", 0) or 0)
        content_item["create_time"] = int(content_item.get("create_time", 0) or 0)

        async with get_session() as session:
            result = await session.execute(select(BilibiliVideo).where(BilibiliVideo.video_id == video_id))
            video_detail = result.scalar_one_or_none()

            if not video_detail:
                content_item["add_ts"] = utils.get_current_timestamp()
                content_item["last_modify_ts"] = utils.get_current_timestamp()
                new_content = BilibiliVideo(**content_item)
                session.add(new_content)
            else:
                content_item["last_modify_ts"] = utils.get_current_timestamp()
                for key, value in content_item.items():
                    setattr(video_detail, key, value)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """
        Bilibili评论数据库存储实现
        Args:
            comment_item: 评论项字典
        """
        comment_id = int(comment_item.get("comment_id"))
        comment_item["comment_id"] = comment_id
        comment_item["video_id"] = int(comment_item.get("video_id", 0) or 0)
        comment_item["create_time"] = int(comment_item.get("create_time", 0) or 0)
        comment_item["like_count"] = str(comment_item.get("like_count", "0"))
        comment_item["sub_comment_count"] = str(comment_item.get("sub_comment_count", "0"))
        comment_item["parent_comment_id"] = str(comment_item.get("parent_comment_id", "0"))

        async with get_session() as session:
            result = await session.execute(select(BilibiliVideoComment).where(BilibiliVideoComment.comment_id == comment_id))
            comment_detail = result.scalar_one_or_none()

            if not comment_detail:
                comment_item["add_ts"] = utils.get_current_timestamp()
                comment_item["last_modify_ts"] = utils.get_current_timestamp()
                new_comment = BilibiliVideoComment(**comment_item)
                session.add(new_comment)
            else:
                comment_item["last_modify_ts"] = utils.get_current_timestamp()
                for key, value in comment_item.items():
                    setattr(comment_detail, key, value)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """
        Bilibili创作者数据库存储实现
        Args:
            creator: 创作者项字典
        """
        creator_id = int(creator.get("user_id"))
        creator["user_id"] = creator_id
        creator["total_fans"] = int(creator.get("total_fans", 0) or 0)
        creator["total_liked"] = int(creator.get("total_liked", 0) or 0)
        creator["user_rank"] = int(creator.get("user_rank", 0) or 0)
        creator["is_official"] = int(creator.get("is_official", 0) or 0)

        async with get_session() as session:
            result = await session.execute(select(BilibiliUpInfo).where(BilibiliUpInfo.user_id == creator_id))
            creator_detail = result.scalar_one_or_none()

            if not creator_detail:
                creator["add_ts"] = utils.get_current_timestamp()
                creator["last_modify_ts"] = utils.get_current_timestamp()
                new_creator = BilibiliUpInfo(**creator)
                session.add(new_creator)
            else:
                creator["last_modify_ts"] = utils.get_current_timestamp()
                for key, value in creator.items():
                    setattr(creator_detail, key, value)
            await session.commit()

    async def store_contact(self, contact_item: Dict):
        """
        Bilibili联系人数据库存储实现
        Args:
            contact_item: 联系人项字典
        """
        up_id = int(contact_item.get("up_id"))
        fan_id = int(contact_item.get("fan_id"))
        contact_item["up_id"] = up_id
        contact_item["fan_id"] = fan_id

        async with get_session() as session:
            result = await session.execute(
                select(BilibiliContactInfo).where(BilibiliContactInfo.up_id == up_id, BilibiliContactInfo.fan_id == fan_id)
            )
            contact_detail = result.scalar_one_or_none()

            if not contact_detail:
                contact_item["add_ts"] = utils.get_current_timestamp()
                contact_item["last_modify_ts"] = utils.get_current_timestamp()
                new_contact = BilibiliContactInfo(**contact_item)
                session.add(new_contact)
            else:
                contact_item["last_modify_ts"] = utils.get_current_timestamp()
                for key, value in contact_item.items():
                    setattr(contact_detail, key, value)
            await session.commit()

    async def store_dynamic(self, dynamic_item):
        """
        Bilibili动态数据库存储实现
        Args:
            dynamic_item: 动态项字典
        """
        dynamic_id = int(dynamic_item.get("dynamic_id"))
        dynamic_item["dynamic_id"] = dynamic_id

        async with get_session() as session:
            result = await session.execute(select(BilibiliUpDynamic).where(BilibiliUpDynamic.dynamic_id == dynamic_id))
            dynamic_detail = result.scalar_one_or_none()

            if not dynamic_detail:
                dynamic_item["add_ts"] = utils.get_current_timestamp()
                dynamic_item["last_modify_ts"] = utils.get_current_timestamp()
                new_dynamic = BilibiliUpDynamic(**dynamic_item)
                session.add(new_dynamic)
            else:
                dynamic_item["last_modify_ts"] = utils.get_current_timestamp()
                for key, value in dynamic_item.items():
                    setattr(dynamic_detail, key, value)
            await session.commit()


class BiliJsonStoreImplement(AbstractStore):
    def __init__(self):
        self.file_writer = AsyncFileWriter(
            crawler_type=crawler_type_var.get(),
            platform="bili"
        )

    async def store_content(self, content_item: Dict):
        """
        内容JSON存储实现
        Args:
            content_item:

        Returns:

        """
        await self.file_writer.write_single_item_to_json(
            item=content_item,
            item_type="contents"
        )

    async def store_comment(self, comment_item: Dict):
        """
        评论JSON存储实现
        Args:
            comment_item:

        Returns:

        """
        await self.file_writer.write_single_item_to_json(
            item=comment_item,
            item_type="comments"
        )

    async def store_creator(self, creator: Dict):
        """
        创作者JSON存储实现
        Args:
            creator:

        Returns:

        """
        await self.file_writer.write_single_item_to_json(
            item=creator,
            item_type="creators"
        )

    async def store_contact(self, contact_item: Dict):
        """
        创作者联系人JSON存储实现
        Args:
            contact_item: 创作者的联系人项字典

        Returns:

        """
        await self.file_writer.write_single_item_to_json(
            item=contact_item,
            item_type="contacts"
        )

    async def store_dynamic(self, dynamic_item: Dict):
        """
        创作者动态JSON存储实现
        Args:
            dynamic_item: 创作者的联系人项字典

        Returns:

        """
        await self.file_writer.write_single_item_to_json(
            item=dynamic_item,
            item_type="dynamics"
        )



class BiliJsonlStoreImplement(AbstractStore):
    def __init__(self):
        self.file_writer = AsyncFileWriter(
            crawler_type=crawler_type_var.get(),
            platform="bili"
        )

    async def store_content(self, content_item: Dict):
        await self.file_writer.write_to_jsonl(
            item=content_item,
            item_type="contents"
        )

    async def store_comment(self, comment_item: Dict):
        await self.file_writer.write_to_jsonl(
            item=comment_item,
            item_type="comments"
        )

    async def store_creator(self, creator: Dict):
        await self.file_writer.write_to_jsonl(
            item=creator,
            item_type="creators"
        )

    async def store_contact(self, contact_item: Dict):
        await self.file_writer.write_to_jsonl(
            item=contact_item,
            item_type="contacts"
        )

    async def store_dynamic(self, dynamic_item: Dict):
        await self.file_writer.write_to_jsonl(
            item=dynamic_item,
            item_type="dynamics"
        )


class BiliSqliteStoreImplement(BiliDbStoreImplement):
    pass


class BiliMongoStoreImplement(AbstractStore):
    """Bilibili MongoDB存储实现"""

    def __init__(self):
        self.mongo_store = MongoDBStoreBase(collection_prefix="bilibili")

    async def store_content(self, content_item: Dict):
        """
        将视频内容存储到MongoDB
        Args:
            content_item: 视频内容数据
        """
        video_id = content_item.get("video_id")
        if not video_id:
            return

        await self.mongo_store.save_or_update(
            collection_suffix="contents",
            query={"video_id": video_id},
            data=content_item
        )
        utils.logger.info(f"[BiliMongoStoreImplement.store_content] 已保存视频 {video_id} 到MongoDB")

    async def store_comment(self, comment_item: Dict):
        """
        将评论存储到MongoDB
        Args:
            comment_item: 评论数据
        """
        comment_id = comment_item.get("comment_id")
        if not comment_id:
            return

        await self.mongo_store.save_or_update(
            collection_suffix="comments",
            query={"comment_id": comment_id},
            data=comment_item
        )
        utils.logger.info(f"[BiliMongoStoreImplement.store_comment] 已保存评论 {comment_id} 到MongoDB")

    async def store_creator(self, creator_item: Dict):
        """
        将UP主信息存储到MongoDB
        Args:
            creator_item: UP主数据
        """
        user_id = creator_item.get("user_id")
        if not user_id:
            return

        await self.mongo_store.save_or_update(
            collection_suffix="creators",
            query={"user_id": user_id},
            data=creator_item
        )
        utils.logger.info(f"[BiliMongoStoreImplement.store_creator] Saved creator {user_id} to MongoDB")


class BiliExcelStoreImplement:
    """Bilibili Excel存储实现 - 全局单例"""

    def __new__(cls, *args, **kwargs):
        from store.excel_store_base import ExcelStoreBase
        return ExcelStoreBase.get_instance(
            platform="bilibili",
            crawler_type=crawler_type_var.get()
        )
