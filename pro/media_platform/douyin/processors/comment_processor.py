# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/douyin/processors/comment_processor.py
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
from asyncio import Task
from typing import List, TYPE_CHECKING

import config
from config.base_config import PER_NOTE_MAX_COMMENTS_COUNT
from model.m_douyin import DouyinAwemeComment
from pkg.tools import utils
from repo.platform_save_data import douyin as douyin_store
from ..exception import DataFetchError

if TYPE_CHECKING:
    from ..client import DouYinApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class CommentProcessor:
    """Handles comment processing operations including batch processing"""

    def __init__(
        self,
        dy_client: "DouYinApiClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_comment_semaphore: asyncio.Semaphore
    ):
        """
        Initialize comment processor

        Args:
            dy_client: Douyin API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_comment_semaphore: Semaphore to limit concurrent comment tasks
        """
        self.dy_client = dy_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_comment_semaphore = crawler_comment_semaphore


    async def batch_get_aweme_comments(
        self,
        aweme_list: List[str],
        checkpoint_id: str,
    ):
        """
        Batch get aweme comments
        Args:
            aweme_list: List of aweme IDs
            checkpoint_id: Checkpoint ID

        Returns:
            None
        """
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.batch_get_aweme_comments] Crawling comment mode is not enabled"
            )
            return

        utils.logger.info(
            f"[CommentProcessor.batch_get_aweme_comments] Begin batch get aweme comments, aweme list: {aweme_list}"
        )
        task_list: List[Task] = []
        for aweme_id in aweme_list:
            if not aweme_id:
                continue

            # 先判断checkpoint中该aweme的is_success_crawled_comments是否为True，如果为True，则跳过
            if await self.checkpoint_manager.check_note_comments_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=aweme_id
            ):
                utils.logger.info(
                    f"[CommentProcessor.batch_get_aweme_comments] Aweme {aweme_id} is already crawled comments, skip"
                )
                continue

            task = asyncio.create_task(
                self.get_comments_async_task(
                    aweme_id,
                    checkpoint_id=checkpoint_id,
                ),
                name=aweme_id,
            )
            task_list.append(task)

        if len(task_list) > 0:
            await asyncio.wait(task_list)

    async def get_comments_async_task(
        self,
        aweme_id: str,
        checkpoint_id: str = "",
    ):
        """
        Get aweme comments with keyword filtering and quantity limitation
        Args:
            aweme_id: aweme id
            checkpoint_id: checkpoint id

        Returns:
            None
        """
        async with self.crawler_comment_semaphore:
            try:
                utils.logger.info(
                    f"[CommentProcessor.get_comments_async_task] Begin get aweme id comments {aweme_id}"
                )
                # 获取视频的所有评论
                await self.get_aweme_all_comments(
                    aweme_id=aweme_id,
                    checkpoint_id=checkpoint_id
                )
                utils.logger.info(
                    f"[CommentProcessor.get_comments_async_task] aweme_id: {aweme_id} comments have all been obtained and filtered ..."
                )
            except DataFetchError as e:
                utils.logger.error(
                    f"[CommentProcessor.get_comments_async_task] aweme_id: {aweme_id} get comments failed, error: {e}"
                )

    async def get_aweme_all_comments(
        self,
        aweme_id: str,
        checkpoint_id: str = ""
    ):
        """
        获取视频的所有评论
        Args:
            aweme_id: 视频ID
            checkpoint_id: 检查点ID

        Returns:
            List of comments
        """
        result = []
        comments_has_more = 1
        comments_cursor = 0

        # 从checkpoint中获取上次保存的评论游标
        if checkpoint_id:
            latest_comment_cursor = await self.checkpoint_manager.get_note_comment_cursor(
                checkpoint_id=checkpoint_id, note_id=aweme_id
            )
            if latest_comment_cursor:
                try:
                    # 将字符串类型的cursor转换为整数类型（Douyin API需要整数）
                    comments_cursor = int(latest_comment_cursor)
                    utils.logger.info(
                        f"[CommentProcessor.get_aweme_all_comments] Resume from latest comment cursor: {comments_cursor}"
                    )
                except (ValueError, TypeError):
                    utils.logger.warning(
                        f"[CommentProcessor.get_aweme_all_comments] Invalid cursor format: {latest_comment_cursor}, starting from beginning"
                    )
                    comments_cursor = 0

        while comments_has_more:
            comments, comments_res = await self.dy_client.get_aweme_comments(aweme_id, comments_cursor)
            comments_has_more = comments_res.get("has_more", 0)
            comments_cursor = comments_res.get("cursor", 0)

            # 更新评论游标到checkpoint中（将整数转换为字符串存储）
            if checkpoint_id and comments_cursor:
                await self.checkpoint_manager.update_note_comment_cursor(
                    checkpoint_id=checkpoint_id,
                    note_id=aweme_id,
                    comment_cursor=str(comments_cursor),
                )

            if not comments:
                continue
            result.extend(comments)
            # 保存评论到数据库
            await douyin_store.batch_update_dy_aweme_comments(aweme_id, comments)
            if (
                PER_NOTE_MAX_COMMENTS_COUNT
                and len(result) >= PER_NOTE_MAX_COMMENTS_COUNT
            ):
                utils.logger.info(
                    f"[CommentProcessor.get_aweme_all_comments] The number of comments exceeds the limit: {PER_NOTE_MAX_COMMENTS_COUNT}"
                )
                break
            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
            sub_comments = await self.get_comments_all_sub_comments(
                aweme_id, comments
            )
            result.extend(sub_comments)

        # 标记该aweme的评论已完全爬取
        if checkpoint_id:
            await self.checkpoint_manager.update_note_comment_cursor(
                checkpoint_id=checkpoint_id,
                note_id=aweme_id,
                comment_cursor=str(comments_cursor),
                is_success_crawled_comments=True,
            )

        return result

    async def get_comments_all_sub_comments(
        self,
        aweme_id: str,
        comments: List[DouyinAwemeComment]
    ) -> List[DouyinAwemeComment]:
        """
        获取指定一级评论下的所有二级评论, 该方法会一直查找一级评论下的所有二级评论信息
        Args:
            aweme_id: 视频ID
            comments: 评论列表

        Returns:
            List of sub-comments
        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.get_comments_all_sub_comments] Crawling sub_comment mode is not enabled"
            )
            return []
        result = []
        for comment in comments:
            reply_comment_total = int(comment.sub_comment_count) if comment.sub_comment_count else 0
            if reply_comment_total > 0:
                comment_id = comment.comment_id
                sub_comments_has_more = 1
                sub_comments_cursor = 0
                while sub_comments_has_more:
                    sub_comments, sub_comments_res = await self.dy_client.get_sub_comments(
                        comment_id, sub_comments_cursor, aweme_id
                    )
                    sub_comments_has_more = sub_comments_res.get("has_more", 0)
                    sub_comments_cursor = sub_comments_res.get("cursor", 0)
                    if not sub_comments:
                        continue
                    result.extend(sub_comments)
                    # 保存子评论到数据库
                    await douyin_store.batch_update_dy_aweme_comments(aweme_id, sub_comments)

                    # 爬虫请求间隔时间
                    await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
        return result
