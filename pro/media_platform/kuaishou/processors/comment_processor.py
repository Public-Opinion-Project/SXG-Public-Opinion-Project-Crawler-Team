# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/kuaishou/processors/comment_processor.py
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
from typing import Dict, List, Optional, Callable, TYPE_CHECKING

import config
from config import PER_NOTE_MAX_COMMENTS_COUNT
from model.m_kuaishou import KuaishouVideoComment
from pkg.tools import utils
from repo.platform_save_data import kuaishou as kuaishou_store
from ..exception import DataFetchError

if TYPE_CHECKING:
    from ..client import KuaiShouApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class CommentProcessor:
    """Handles comment processing operations including fetching and checkpoint management"""

    def __init__(
        self,
        ks_client: "KuaiShouApiClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_comment_semaphore: asyncio.Semaphore
    ):
        """
        Initialize comment processor

        Args:
            ks_client: Kuaishou API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_comment_semaphore: Semaphore to limit concurrent comment tasks
        """
        self.ks_client = ks_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_comment_semaphore = crawler_comment_semaphore

    async def batch_get_video_comments(
        self,
        video_id_list: List[str],
        checkpoint_id: str = "",
    ) -> None:
        """
        Batch get video comments with checkpoint support

        Args:
            video_id_list: List of video IDs
            checkpoint_id: checkpoint id for resume functionality

        Returns:
            None
        """
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.batch_get_video_comments] Crawling comment mode is not enabled"
            )
            return

        utils.logger.info(
            f"[CommentProcessor.batch_get_video_comments] video ids:{video_id_list}"
        )

        task_list: List[Task] = []
        for video_id in video_id_list:
            if not video_id:
                continue

            task = asyncio.create_task(
                self.get_comments_async_task(video_id, checkpoint_id), name=video_id
            )
            task_list.append(task)

        await asyncio.gather(*task_list)

    async def get_comments_async_task(
        self,
        video_id: str,
        checkpoint_id: str = "",
    ) -> None:
        """
        Get comments for video id with checkpoint support

        Args:
            video_id: video id
            checkpoint_id: checkpoint id for resume functionality

        Returns:
            None
        """
        async with self.crawler_comment_semaphore:
            try:
                utils.logger.info(
                    f"[CommentProcessor.get_comments_async_task] Begin get video id comments {video_id}"
                )
                # 获取视频的所有评论
                await self.get_video_all_comments(
                    photo_id=video_id,
                    checkpoint_id=checkpoint_id
                )
                utils.logger.info(
                    f"[CommentProcessor.get_comments_async_task] video_id: {video_id} comments have all been obtained and filtered ..."
                )
            except DataFetchError as e:
                utils.logger.error(
                    f"[CommentProcessor.get_comments_async_task] video_id: {video_id} get comments failed, error: {e}"
                )
            except Exception as e:
                utils.logger.error(
                    f"[CommentProcessor.get_comments_async_task] may be been blocked, err:{e}"
                )

    async def get_video_all_comments(
        self,
        photo_id: str,
        checkpoint_id: str = "",
    ) -> List[KuaishouVideoComment]:
        """
        获取视频所有评论，包括一级评论和二级评论，支持断点续传
        使用V2 REST API

        Args:
            photo_id: 视频ID
            checkpoint_id: checkpoint id for resume functionality

        Returns:
            List[KuaishouVideoComment]: 评论模型列表
        """
        result = []
        pcursor = ""

        # 从checkpoint中获取上次保存的评论游标
        if checkpoint_id:
            latest_comment_cursor = await self.checkpoint_manager.get_note_comment_cursor(
                checkpoint_id=checkpoint_id, note_id=photo_id
            )
            if latest_comment_cursor:
                pcursor = latest_comment_cursor
                utils.logger.info(
                    f"[CommentProcessor.get_video_all_comments] Resume from latest comment cursor: {pcursor}"
                )

        while pcursor != "no_more":
            try:
                # 使用V2 API获取评论
                comments, comments_res = await self.ks_client.get_video_comments_v2(photo_id, pcursor)

                # V2 API使用pcursorV2
                pcursor = comments_res.get("pcursorV2", "no_more")
                raw_comments = comments_res.get("rootCommentsV2", [])

                if not comments:
                    continue

                # 保存评论到数据库
                await kuaishou_store.batch_update_ks_video_comments(comments)
                result.extend(comments)

                # 更新checkpoint中的评论游标
                await self.checkpoint_manager.update_note_comment_cursor(
                    checkpoint_id=checkpoint_id,
                    note_id=photo_id,
                    comment_cursor=pcursor,
                    is_success_crawled_comments=False,
                )

                if (
                    PER_NOTE_MAX_COMMENTS_COUNT
                    and len(result) >= PER_NOTE_MAX_COMMENTS_COUNT
                ):
                    utils.logger.info(
                        f"[CommentProcessor.get_video_all_comments] The number of comments exceeds the limit: {PER_NOTE_MAX_COMMENTS_COUNT}"
                    )
                    break

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

                # 获取子评论 - 使用V2版本
                sub_comments = await self.get_comments_all_sub_comments(
                    comments, raw_comments, photo_id
                )
                result.extend(sub_comments)

            except Exception as e:
                utils.logger.error(
                    f"[CommentProcessor.get_video_all_comments] Error getting comments for {photo_id}: {e}"
                )
                return result

        # 标记该video的评论已完全爬取
        await self.checkpoint_manager.update_note_comment_cursor(
            checkpoint_id=checkpoint_id,
            note_id=photo_id,
            comment_cursor=pcursor,
            is_success_crawled_comments=True,
        )

        return result

    async def get_comments_all_sub_comments(
        self,
        comments: List[KuaishouVideoComment],
        raw_comments: List[Dict],
        photo_id: str,
    ) -> List[KuaishouVideoComment]:
        """
        获取指定一级评论下的所有二级评论, 该方法会一直查找一级评论下的所有二级评论信息
        使用V2 REST API

        Args:
            comments: 评论模型列表
            raw_comments: 原始评论数据（V2版本，用于判断是否有子评论）
            photo_id: 视频ID

        Returns:
            List[KuaishouVideoComment]: 子评论模型列表
        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.get_comments_all_sub_comments] Crawling sub_comment mode is not enabled"
            )
            return []

        result = []
        # 使用raw_comments获取子评论信息，使用comments获取评论ID
        for comment, raw_comment in zip(comments, raw_comments):
            # V2 API使用hasSubComments布尔值判断是否有子评论
            has_sub_comments = raw_comment.get("hasSubComments", False)
            if not has_sub_comments:
                continue

            root_comment_id = comment.comment_id
            sub_comment_pcursor = ""

            while sub_comment_pcursor != "no_more":
                try:
                    # 使用V2 API获取子评论
                    sub_comments, sub_comments_res = await self.ks_client.get_video_sub_comments_v2(
                        photo_id, root_comment_id, sub_comment_pcursor
                    )

                    # V2 API使用pcursorV2
                    sub_comment_pcursor = sub_comments_res.get("pcursorV2", "no_more")

                    if sub_comments:
                        await kuaishou_store.batch_update_ks_video_comments(sub_comments)
                        result.extend(sub_comments)

                    # 爬虫请求间隔时间
                    await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
                except Exception as e:
                    utils.logger.error(
                        f"[CommentProcessor.get_comments_all_sub_comments] Error getting sub comments: {e}"
                    )
                    break
        return result
