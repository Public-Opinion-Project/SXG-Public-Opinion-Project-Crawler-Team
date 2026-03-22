# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/tieba/processors/comment_processor.py
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
from typing import List, TYPE_CHECKING, Callable, Optional

import config
from config import PER_NOTE_MAX_COMMENTS_COUNT
from model.m_baidu_tieba import TiebaNote, TiebaComment
from pkg.tools import utils
from repo.platform_save_data import tieba as tieba_store

if TYPE_CHECKING:
    from ..client import BaiduTieBaClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class CommentProcessor:
    """Handles comment processing operations including batch processing and sub-comments"""

    def __init__(
            self,
            tieba_client: "BaiduTieBaClient",
            checkpoint_manager: "CheckpointRepoManager",
            crawler_note_comment_semaphore: asyncio.Semaphore
    ):
        """
        Initialize comment processor

        Args:
            tieba_client: Tieba API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_note_comment_semaphore: Semaphore to limit concurrent comment tasks
        """
        self.tieba_client = tieba_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_note_comment_semaphore = crawler_note_comment_semaphore

    async def batch_get_note_comments(
            self,
            note_detail_list: List[TiebaNote],
            checkpoint_id: str = "",
    ):
        """
        Batch get note comments
        Args:
            note_detail_list: List of note details
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
            f"[CommentProcessor.batch_get_note_comments] Begin batch get note comments, note list: {[note.note_id for note in note_detail_list]}"
        )
        task_list: List[Task] = []
        for note_detail in note_detail_list:
            # 先判断checkpoint中该note的is_success_crawled_comments是否为True，如果为True，则跳过
            if await self.checkpoint_manager.check_note_comments_is_crawled_in_checkpoint(
                    checkpoint_id=checkpoint_id, note_id=note_detail.note_id
            ):
                utils.logger.info(
                    f"[CommentProcessor.batch_get_note_comments] Note {note_detail.note_id} is already crawled comments, skip"
                )
                continue

            task = asyncio.create_task(
                self.get_comments_async_task(
                    note_detail,
                    checkpoint_id=checkpoint_id,
                ),
                name=note_detail.note_id,
            )
            task_list.append(task)
        await asyncio.gather(*task_list)

    async def get_comments_async_task(
            self,
            note_detail: TiebaNote,
            checkpoint_id: str = "",
    ):
        """
        Get comments async task
        Args:
            note_detail: Note detail object
            checkpoint_id: checkpoint id

        Returns:
            None
        """
        async with self.crawler_note_comment_semaphore:
            utils.logger.info(
                f"[CommentProcessor.get_comments_async_task] Begin get note id comments {note_detail.note_id}"
            )
            await self.get_note_all_comments(
                note_detail=note_detail,
                callback=tieba_store.batch_update_tieba_note_comments,
                checkpoint_id=checkpoint_id,
            )

    async def get_note_all_comments(
            self,
            note_detail: TiebaNote,
            callback: Optional[Callable] = None,
            checkpoint_id: str = ""
    ) -> List[TiebaComment]:
        """
        获取指定帖子下的所有一级评论，该方法会一直查找一个帖子下的所有评论信息
        Args:
            note_detail: 帖子详情对象
            callback: 一次笔记爬取结束后
            checkpoint_id: 检查点ID

        Returns:

        """
        result: List[TiebaComment] = []
        current_page = 1
        note_id = note_detail.note_id
        lastest_comment_cursor = await self.checkpoint_manager.get_note_comment_cursor(
            checkpoint_id=checkpoint_id, note_id=note_id
        )
        if lastest_comment_cursor:
            utils.logger.info(
                f"[CommentProcessor.get_note_all_comments] Lastest comment cursor: {lastest_comment_cursor}"
            )
            current_page = int(lastest_comment_cursor)

        while note_detail.total_replay_page >= current_page:
            response_txt = await self.tieba_client.get_note_comments(note_id, current_page)
            comments: List[TiebaComment] = self.tieba_client.page_extractor.extract_tieba_note_parment_comments(
                response_txt, note_id=note_detail.note_id
            )
            if not comments:
                break

            if callback:
                await callback(note_detail.note_id, comments)

            result.extend(comments)
            if (
                    PER_NOTE_MAX_COMMENTS_COUNT
                    and len(result) >= PER_NOTE_MAX_COMMENTS_COUNT
            ):
                utils.logger.info(
                    f"[CommentProcessor.get_note_all_comments] The number of comments exceeds the limit: {PER_NOTE_MAX_COMMENTS_COUNT}"
                )
                break

            current_page += 1
            await self.checkpoint_manager.update_note_comment_cursor(
                checkpoint_id=checkpoint_id,
                note_id=note_id,
                comment_cursor=str(current_page),
            )

            # 获取所有子评论
            await self.get_comments_all_sub_comments(
                comments, callback=callback
            )
            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

        # 更新评论游标，标记为该帖子的评论已爬取
        await self.checkpoint_manager.update_note_comment_cursor(
            checkpoint_id=checkpoint_id,
            note_id=note_id,
            comment_cursor=str(current_page),
            is_success_crawled_comments=True,
        )

        return result

    async def get_comments_all_sub_comments(
            self,
            comments: List[TiebaComment],
            callback: Optional[Callable] = None,
    ) -> List[TiebaComment]:
        """
        获取指定评论下的所有子评论
        Args:
            comments: 评论列表
            callback: 一次笔记爬取结束后

        Returns:

        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            return []

        all_sub_comments: List[TiebaComment] = []
        for parment_comment in comments:
            if parment_comment.sub_comment_count == 0:
                continue

            current_page = 1
            max_sub_page_num = parment_comment.sub_comment_count // 10 + 1
            while max_sub_page_num >= current_page:
                response_txt = await self.tieba_client.get_note_sub_comments(parment_comment.note_id, parment_comment.tieba_id,
                                                              current_page)

                sub_comments: List[TiebaComment] = self.tieba_client.page_extractor.extract_tieba_note_sub_comments(
                    response_txt, parment_comment
                )
                if not sub_comments:
                    break

                if callback:
                    await callback(parment_comment.note_id, sub_comments)

                all_sub_comments.extend(sub_comments)
                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
                current_page += 1

        return all_sub_comments
