# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/xhs/processors/comment_processor.py
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
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

import config
from config.base_config import PER_NOTE_MAX_COMMENTS_COUNT
from model.m_xhs import XhsComment
from pkg.tools import utils
from repo.platform_save_data import xhs as xhs_store

if TYPE_CHECKING:
    from ..client import XiaoHongShuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class CommentProcessor:
    """Handles comment processing operations including batch processing and sub-comments"""

    def __init__(
        self,
        xhs_client: "XiaoHongShuClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_note_comment_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize comment processor

        Args:
            xhs_client: XiaoHongShu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_note_comment_semaphore: Semaphore to limit concurrent comment tasks
        """
        self.xhs_client = xhs_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_note_comment_semaphore = crawler_note_comment_semaphore

    async def batch_get_note_comments(
        self,
        note_list: List[str],
        xsec_tokens=None,
        checkpoint_id: str = "",
    ):
        """
        Batch get note comments
        Args:
            note_list: List of note IDs
            xsec_tokens: List of xsec tokens
            checkpoint_id: Checkpoint ID

        Returns:
            None
        """
        if xsec_tokens is None:
            xsec_tokens = []
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.batch_get_note_comments] Crawling comment mode is not enabled"
            )
            return

        utils.logger.info(
            f"[CommentProcessor.batch_get_note_comments] Begin batch get note comments, note list: {note_list}"
        )
        task_list: List[Task] = []
        for index, note_id in enumerate(note_list):

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
                    xsec_token=xsec_tokens[index],
                    checkpoint_id=checkpoint_id,
                ),
                name=note_id,
            )
            task_list.append(task)
        await asyncio.gather(*task_list)

    async def get_comments_async_task(
        self,
        note_id: str,
        xsec_token: str = "",
        checkpoint_id: str = "",
    ):
        """
        Get note comments with keyword filtering and quantity limitation
        Args:
            note_id: note id
            xsec_token: xsec token
            checkpoint_id: checkpoint id

        Returns:
            None
        """
        async with self.crawler_note_comment_semaphore:
            utils.logger.info(
                f"[CommentProcessor.get_comments_async_task] Begin get note id comments {note_id}"
            )
            await self.get_note_all_comments(
                note_id=note_id,
                xsec_token=xsec_token,
                checkpoint_id=checkpoint_id,
            )

    async def get_note_all_comments(
        self,
        note_id: str,
        xsec_token: str = "",
        checkpoint_id: str = "",
    ) -> List[XhsComment]:
        """
        获取指定笔记下的所有一级评论，该方法会一直查找一个帖子下的所有评论信息
        Args:
            note_id: 笔记ID
            callback: 一次笔记爬取结束后
            xsec_token: 验证token
            checkpoint_id: 检查点ID

        Returns:
            List[XhsComment]: 评论模型列表
        """
        current_comment_cursor = ""
        lastest_comment_cursor = await self.checkpoint_manager.get_note_comment_cursor(
            checkpoint_id=checkpoint_id, note_id=note_id
        )
        if lastest_comment_cursor:
            utils.logger.info(
                f"[CommentProcessor.get_note_all_comments] Lastest comment cursor: {lastest_comment_cursor}"
            )
            current_comment_cursor = lastest_comment_cursor

        result = []
        comments_has_more = True
        comments_cursor = current_comment_cursor  # 首次用外部传入的 cursor

        utils.logger.info(
            f"[CommentProcessor.get_note_all_comments] Begin get note {note_id} all comments, current_comment_cursor: {current_comment_cursor}"
        )

        while comments_has_more:
            comments, comments_res = await self.xhs_client.get_note_comments(
                note_id, comments_cursor, xsec_token
            )
            comments_has_more = comments_res.get("has_more", False)
            comments_cursor = comments_res.get("cursor", "")

            # 更新评论游标到checkpoint中
            if comments_cursor:
                await self.checkpoint_manager.update_note_comment_cursor(
                    checkpoint_id=checkpoint_id,
                    note_id=note_id,
                    comment_cursor=comments_cursor,
                )

            if not comments:
                continue

            # 保存评论到数据库
            await xhs_store.batch_update_xhs_note_comments(comments)

            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            result.extend(comments)

            if (
                PER_NOTE_MAX_COMMENTS_COUNT
                and len(result) >= PER_NOTE_MAX_COMMENTS_COUNT
            ):
                utils.logger.info(
                    f"[CommentProcessor.get_note_all_comments] The number of comments exceeds the limit: {PER_NOTE_MAX_COMMENTS_COUNT}"
                )
                break
            sub_comments = await self.get_comments_all_sub_comments(
                note_id, comments, comments_res.get("comments", []), xsec_token
            )
            result.extend(sub_comments)

        # 更新评论游标，标记为该帖子的评论已爬取
        await self.checkpoint_manager.update_note_comment_cursor(
            checkpoint_id=checkpoint_id,
            note_id=note_id,
            comment_cursor=comments_cursor,
            is_success_crawled_comments=True,
        )

        return result

    async def get_comments_all_sub_comments(
        self,
        note_id: str,
        comments: List[XhsComment],
        raw_comments: List[Dict],
        xsec_token: str = "",
    ) -> List[XhsComment]:
        """
        获取指定一级评论下的所有二级评论, 该方法会一直查找一级评论下的所有二级评论信息
        Args:
            note_id: 笔记ID
            comments: 评论模型列表
            raw_comments: 原始评论数据（用于获取游标信息）
            xsec_token: 验证token

        Returns:
            List[XhsComment]: 子评论模型列表
        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.get_comments_all_sub_comments] Crawling sub_comment mode is not enabled"
            )
            return []

        result = []
        # 使用raw_comments获取游标信息，使用comments获取评论ID
        for comment, raw_comment in zip(comments, raw_comments):
            sub_comments_data = raw_comment.get("sub_comments")
            if sub_comments_data:
                # 转换子评论为模型并保存
                sub_comments_models = self.xhs_client._extractor.extract_comments_from_dict(
                    note_id, sub_comments_data, xsec_token, comment.comment_id
                )
                await xhs_store.batch_update_xhs_note_comments(sub_comments_models)
                result.extend(sub_comments_models)

            sub_comment_has_more = raw_comment.get("sub_comment_has_more")
            if not sub_comment_has_more:
                continue

            root_comment_id = comment.comment_id
            sub_comment_cursor = raw_comment.get("sub_comment_cursor")

            while sub_comment_has_more:
                sub_comments, sub_comments_res = await self.xhs_client.get_note_sub_comments(
                    note_id,
                    root_comment_id,
                    10,
                    sub_comment_cursor,
                    xsec_token,
                )
                sub_comment_has_more = sub_comments_res.get("has_more", False)
                sub_comment_cursor = sub_comments_res.get("cursor", "")

                if not sub_comments:
                    continue

                # 保存子评论到数据库
                await xhs_store.batch_update_xhs_note_comments(sub_comments)

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
                result.extend(sub_comments)
        return result
