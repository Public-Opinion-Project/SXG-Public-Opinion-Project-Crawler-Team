# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
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
from model.m_zhihu import ZhihuComment, ZhihuContent
from pkg.tools import utils
from repo.platform_save_data import zhihu as zhihu_store
from ..help import ZhihuExtractor

if TYPE_CHECKING:
    from ..client import ZhiHuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class CommentProcessor:
    """Handles comment processing operations for Zhihu platform"""

    def __init__(
        self,
        zhihu_client: "ZhiHuClient",
        checkpoint_manager: "CheckpointRepoManager",
        comment_task_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize comment processor

        Args:
            zhihu_client: Zhihu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            comment_task_semaphore: Semaphore to limit concurrent comment tasks
        """
        self.zhihu_client = zhihu_client
        self.checkpoint_manager = checkpoint_manager
        self.comment_task_semaphore = comment_task_semaphore
        self._extractor = ZhihuExtractor()

    async def batch_get_content_comments(
        self,
        content_list: List[ZhihuContent],
        checkpoint_id: str = "",
    ):
        """
        Batch get comments for content list

        Args:
            content_list: List of ZhihuContent objects
            checkpoint_id: Checkpoint ID

        Returns:
            None
        """
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.batch_get_content_comments] Crawling comment mode is not enabled"
            )
            return

        utils.logger.info(
            f"[CommentProcessor.batch_get_content_comments] Begin batch get comments for {len(content_list)} contents"
        )

        task_list: List[Task] = []
        for content in content_list:
            if not content or not content.content_id:
                continue

            # Check if comments are already crawled
            if await self.checkpoint_manager.check_note_comments_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=content.content_id
            ):
                utils.logger.info(
                    f"[CommentProcessor.batch_get_content_comments] Content {content.content_id} comments already crawled, skip"
                )
                continue

            task = asyncio.create_task(
                self._get_comments_async_task(content, checkpoint_id),
                name=content.content_id,
            )
            task_list.append(task)

        if task_list:
            await asyncio.gather(*task_list)

    async def _get_comments_async_task(
        self,
        content: ZhihuContent,
        checkpoint_id: str = "",
    ):
        """
        Get content comments with semaphore control

        Args:
            content: ZhihuContent object
            checkpoint_id: Checkpoint ID

        Returns:
            None
        """
        async with self.comment_task_semaphore:
            utils.logger.info(
                f"[CommentProcessor._get_comments_async_task] Begin get comments for content {content.content_id}"
            )
            await self._get_all_comments(content, checkpoint_id)

    async def _get_all_comments(
        self,
        content: ZhihuContent,
        checkpoint_id: str = "",
    ) -> List[ZhihuComment]:
        """
        Get all comments for a content with checkpoint support

        Args:
            content: ZhihuContent object
            checkpoint_id: Checkpoint ID

        Returns:
            List of ZhihuComment objects
        """
        # Get last comment cursor from checkpoint
        current_cursor = ""
        last_cursor = await self.checkpoint_manager.get_note_comment_cursor(
            checkpoint_id=checkpoint_id, note_id=content.content_id
        )
        if last_cursor:
            utils.logger.info(
                f"[CommentProcessor._get_all_comments] Resume from cursor: {last_cursor}"
            )
            current_cursor = last_cursor

        result: List[ZhihuComment] = []
        is_end = False
        offset = current_cursor
        limit = 10

        while not is_end:
            try:
                root_comment_res = await self.zhihu_client.get_root_comments(
                    content.content_id, content.content_type, offset, limit
                )

                if not root_comment_res:
                    break

                paging_info = root_comment_res.get("paging", {})
                is_end = paging_info.get("is_end", True)

                # Extract offset from next URL
                offset = self._extractor.extract_offset(paging_info)

                # Update comment cursor in checkpoint
                if offset:
                    await self.checkpoint_manager.update_note_comment_cursor(
                        checkpoint_id=checkpoint_id,
                        note_id=content.content_id,
                        comment_cursor=offset,
                    )

                comments = self._extractor.extract_comments(
                    content, root_comment_res.get("data", [])
                )

                if not comments:
                    break

                # Save comments to database
                await zhihu_store.batch_update_zhihu_note_comments(comments)
                result.extend(comments)

                # Get sub comments if enabled
                if config.ENABLE_GET_SUB_COMMENTS:
                    sub_comments = await self._get_all_sub_comments(content, comments)
                    result.extend(sub_comments)

                # Crawler request interval
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            except Exception as ex:
                utils.logger.error(
                    f"[CommentProcessor._get_all_comments] Error: {ex}"
                )
                break

        # Mark comments as fully crawled
        await self.checkpoint_manager.update_note_comment_cursor(
            checkpoint_id=checkpoint_id,
            note_id=content.content_id,
            comment_cursor=offset,
            is_success_crawled_comments=True,
        )

        utils.logger.info(
            f"[CommentProcessor._get_all_comments] Finished getting {len(result)} comments for content {content.content_id}"
        )

        return result

    async def _get_all_sub_comments(
        self,
        content: ZhihuContent,
        parent_comments: List[ZhihuComment],
    ) -> List[ZhihuComment]:
        """
        Get all sub comments for parent comments

        Args:
            content: ZhihuContent object
            parent_comments: List of parent ZhihuComment objects

        Returns:
            List of sub ZhihuComment objects
        """
        all_sub_comments: List[ZhihuComment] = []

        for parent_comment in parent_comments:
            if not parent_comment.sub_comment_count or parent_comment.sub_comment_count == 0:
                continue

            is_end = False
            offset = ""
            limit = 10

            while not is_end:
                try:
                    child_comment_res = await self.zhihu_client.get_child_comments(
                        parent_comment.comment_id, offset, limit
                    )

                    if not child_comment_res:
                        break

                    paging_info = child_comment_res.get("paging", {})
                    is_end = paging_info.get("is_end", True)
                    offset = self._extractor.extract_offset(paging_info)

                    sub_comments = self._extractor.extract_comments(
                        content, child_comment_res.get("data", [])
                    )

                    if not sub_comments:
                        break

                    # Save sub comments to database
                    await zhihu_store.batch_update_zhihu_note_comments(sub_comments)
                    all_sub_comments.extend(sub_comments)

                    # Crawler request interval
                    await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

                except Exception as ex:
                    utils.logger.error(
                        f"[CommentProcessor._get_all_sub_comments] Error: {ex}"
                    )
                    break

        return all_sub_comments
