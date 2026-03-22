# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/weibo/processors/comment_processor.py
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

import asyncio
import random
from asyncio import Task
from typing import List, TYPE_CHECKING, Dict, Optional, Callable

import config
from config import PER_NOTE_MAX_COMMENTS_COUNT
from pkg.tools import utils
from repo.platform_save_data import weibo as weibo_store
from ..exception import DataFetchError
from model.m_weibo import WeiboComment

if TYPE_CHECKING:
    from ..client import WeiboClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class CommentProcessor:
    """Handles comment processing operations including batch processing and sub-comments"""

    def __init__(
        self,
        wb_client: "WeiboClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_note_comment_semaphore: asyncio.Semaphore
    ):
        """
        Initialize comment processor

        Args:
            wb_client: Weibo API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_note_comment_semaphore: Semaphore to limit concurrent comment tasks
        """
        self.wb_client = wb_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_note_comment_semaphore = crawler_note_comment_semaphore

    async def batch_get_note_comments(
        self,
        note_id_list: List[str],
        checkpoint_id: str = "",
    ):
        """
        Batch get note comments
        Args:
            note_id_list: List of note IDs
            checkpoint_id: Checkpoint ID

        Returns:
            None
        """
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.batch_get_note_comments] Crawling comment mode is not enabled"
            )
            return

        utils.logger.info(
            f"[CommentProcessor.batch_get_note_comments] Begin batch get note comments, note list: {note_id_list}"
        )
        task_list: List[Task] = []
        for note_id in note_id_list:

            # 先判断checkpoint中该note的is_success_crawled_comments是否为True，如果为True，则跳过
            if await self.checkpoint_manager.check_note_comments_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=note_id
            ):
                utils.logger.info(
                    f"[CommentProcessor.batch_get_note_comments] Note {note_id} is already crawled comments, skip"
                )
                continue

            task = asyncio.create_task(
                self.get_comments_async_task(
                    note_id,
                    checkpoint_id=checkpoint_id,
                ),
                name=note_id,
            )
            task_list.append(task)
        await asyncio.gather(*task_list)

    async def get_comments_async_task(
        self,
        note_id: str,
        checkpoint_id: str = "",
    ):
        """
        Get note comments with keyword filtering and quantity limitation
        Args:
            note_id: note id
            checkpoint_id: checkpoint id

        Returns:
            None
        """
        async with self.crawler_note_comment_semaphore:
            utils.logger.info(
                f"[CommentProcessor.get_comments_async_task] Begin get note id comments {note_id}"
            )
            try:
                await self.get_note_all_comments(
                    note_id=note_id,
                    callback=weibo_store.batch_update_weibo_note_comments,
                    checkpoint_id=checkpoint_id
                )

            except DataFetchError as ex:
                utils.logger.error(
                    f"[CommentProcessor.get_comments_async_task] get note_id: {note_id} comment error: {ex}"
                )
            except Exception as e:
                utils.logger.error(
                    f"[CommentProcessor.get_comments_async_task] may be been blocked, err:{e}"
                )



    async def get_note_all_comments(
        self,
        note_id: str,
        callback: Optional[Callable] = None,
        checkpoint_id: str = "",
    ):
        """
        获取指定微博下的所有一级评论，该方法会一直查找一个微博下的所有评论信息
        Args:
            note_id: 微博ID
            callback: 回调函数
            checkpoint_id: 检查点ID

        Returns:

        """

        result = []
        is_end = False
        max_id = -1
        max_id_type = 0

        # 从checkpoint中获取上次保存的评论游标
        if checkpoint_id:
            latest_comment_cursor = await self.checkpoint_manager.get_note_comment_cursor(
                checkpoint_id=checkpoint_id, note_id=note_id
            )
            if latest_comment_cursor:
                max_id = int(latest_comment_cursor)
                utils.logger.info(
                    f"[CommentProcessor.get_note_all_comments] Resume from latest comment cursor: {max_id}"
                )

        while not is_end:
            comments, comments_res = await self.wb_client.get_note_comments(note_id, max_id, max_id_type)
            if not comments_res:
                break
            max_id = comments_res.get("max_id", 0)
            max_id_type = comments_res.get("max_id_type", 0)
            comment_list = comments  # Now WeiboComment models
            is_end = max_id == 0

            # 更新评论游标到checkpoint中（将整数转换为字符串存储）
            if checkpoint_id:
                await self.checkpoint_manager.update_note_comment_cursor(
                    checkpoint_id=checkpoint_id,
                    note_id=note_id,
                    comment_cursor=str(max_id),
                )

            if callback:  # 如果有回调函数，就执行回调函数
                await callback(note_id, comment_list)

            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
            result.extend(comment_list)

            if (
                PER_NOTE_MAX_COMMENTS_COUNT
                and len(result) >= PER_NOTE_MAX_COMMENTS_COUNT
            ):
                utils.logger.info(
                    f"[WeiboClient.get_note_all_comments] The number of comments exceeds the limit: {PER_NOTE_MAX_COMMENTS_COUNT}"
                )
                break

            sub_comment_result = await self.get_comments_all_sub_comments(
                note_id, comment_list, callback
            )
            result.extend(sub_comment_result)


        # 标记该aweme的评论已完全爬取
        if checkpoint_id:
            await self.checkpoint_manager.update_note_comment_cursor(
                checkpoint_id=checkpoint_id,
                note_id=note_id,
                comment_cursor=str(max_id),
                is_success_crawled_comments=True,
            )

        return result

    @staticmethod
    async def get_comments_all_sub_comments(
        note_id: str, comment_list: List[WeiboComment], callback: Optional[Callable] = None
    ) -> List[WeiboComment]:
        """
        获取评论的所有子评论
        Args:
            note_id:
            comment_list:
            callback:

        Returns:

        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            utils.logger.info(
                f"[WeiboClient.get_comments_all_sub_comments] Crawling sub_comment mode is not enabled"
            )
            return []

        res_sub_comments = []
        for comment in comment_list:
            sub_comments = comment.sub_comments or []
            if sub_comments:
                if callback:
                    await callback(note_id, sub_comments)
                res_sub_comments.extend(sub_comments)
        return res_sub_comments
