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
from typing import List, Optional, TYPE_CHECKING

import config
from model.m_zhihu import ZhihuContent
from pkg.tools import utils
from repo.platform_save_data import zhihu as zhihu_store

if TYPE_CHECKING:
    from ..client import ZhiHuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class ContentProcessor:
    """Handles content processing operations for Zhihu platform"""

    def __init__(
        self,
        zhihu_client: "ZhiHuClient",
        checkpoint_manager: "CheckpointRepoManager",
        content_task_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize content processor

        Args:
            zhihu_client: Zhihu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            content_task_semaphore: Semaphore to limit concurrent content tasks
        """
        self.zhihu_client = zhihu_client
        self.checkpoint_manager = checkpoint_manager
        self.content_task_semaphore = content_task_semaphore

    async def batch_process_contents(
        self,
        content_list: List[ZhihuContent],
        checkpoint_id: str = "",
    ) -> List[str]:
        """
        Batch process content list with checkpoint support

        Args:
            content_list: List of ZhihuContent objects
            checkpoint_id: Checkpoint ID for resume functionality

        Returns:
            List of processed content IDs
        """
        task_list = []
        content_ids = []

        for content in content_list:
            if not content or not content.content_id:
                continue

            content_id = content.content_id
            content_ids.append(content_id)

            # Check if content is already crawled
            if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=content_id
            ):
                utils.logger.info(
                    f"[ContentProcessor.batch_process_contents] Content {content_id} is already crawled, skip"
                )
                continue

            # Add content to checkpoint
            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint_id,
                note_id=content_id,
                extra_params_info={
                    "content_type": content.content_type,
                    "question_id": getattr(content, "question_id", None),
                },
            )

            # Create processing task
            task = self._process_single_content(content, checkpoint_id)
            task_list.append(task)

        if task_list:
            await asyncio.gather(*task_list)

        return content_ids

    async def _process_single_content(
        self,
        content: ZhihuContent,
        checkpoint_id: str,
    ) -> Optional[ZhihuContent]:
        """
        Process single content with semaphore control

        Args:
            content: ZhihuContent object
            checkpoint_id: Checkpoint ID

        Returns:
            Processed ZhihuContent or None
        """
        async with self.content_task_semaphore:
            is_success_crawled = False
            try:
                # Save content to database
                await zhihu_store.update_zhihu_content(content)
                utils.logger.info(
                    f"[ContentProcessor._process_single_content] Saved content {content.content_id}"
                )
                is_success_crawled = True
                return content

            except Exception as ex:
                utils.logger.error(
                    f"[ContentProcessor._process_single_content] Process content error: {ex}"
                )
                return None

            finally:
                # Update checkpoint status
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint_id,
                    note_id=content.content_id,
                    is_success_crawled=is_success_crawled,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                )

                # Crawler request interval
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

    async def process_content_by_id(
        self,
        content_id: str,
        content_type: str,
        checkpoint_id: str = "",
        question_id: str = "",
    ) -> Optional[ZhihuContent]:
        """
        Process content by fetching its detail first

        Args:
            content_id: Content ID (answer_id, article_id, or video_id)
            content_type: Content type (answer, article, zvideo)
            checkpoint_id: Checkpoint ID
            question_id: Question ID (only for answer type)

        Returns:
            ZhihuContent or None
        """
        async with self.content_task_semaphore:
            content: Optional[ZhihuContent] = None
            try:
                # Fetch content detail based on type
                if content_type == "answer" and question_id:
                    content = await self.zhihu_client.get_answer_info(
                        question_id, content_id
                    )
                elif content_type == "article":
                    content = await self.zhihu_client.get_article_info(content_id)
                elif content_type == "zvideo":
                    content = await self.zhihu_client.get_video_info(content_id)

                if content:
                    await zhihu_store.update_zhihu_content(content)
                    utils.logger.info(
                        f"[ContentProcessor.process_content_by_id] Saved content {content_id}"
                    )

                return content

            except Exception as ex:
                utils.logger.error(
                    f"[ContentProcessor.process_content_by_id] Error: {ex}"
                )
                return None

            finally:
                # Update checkpoint status
                is_success_crawled = content is not None
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint_id,
                    note_id=content_id,
                    is_success_crawled=is_success_crawled,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                )

                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
