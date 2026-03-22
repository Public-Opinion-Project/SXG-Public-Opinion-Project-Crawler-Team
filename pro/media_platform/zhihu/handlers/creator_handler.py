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
import constant
from model.m_checkpoint import Checkpoint
from model.m_zhihu import ZhihuContent, ZhihuCreator
from pkg.tools import utils
from repo.platform_save_data import zhihu as zhihu_store
from .base_handler import BaseHandler
from ..help import ZhihuExtractor

if TYPE_CHECKING:
    from ..client import ZhiHuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.content_processor import ContentProcessor
    from ..processors.comment_processor import CommentProcessor


class CreatorHandler(BaseHandler):
    """Handles creator-based crawling operations for Zhihu"""

    def __init__(
        self,
        zhihu_client: "ZhiHuClient",
        checkpoint_manager: "CheckpointRepoManager",
        content_processor: "ContentProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize creator handler

        Args:
            zhihu_client: Zhihu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            content_processor: Content processing component
            comment_processor: Comment processing component
        """
        super().__init__(
            zhihu_client, checkpoint_manager, content_processor, comment_processor
        )
        self._extractor = ZhihuExtractor()

    async def handle(self) -> None:
        """
        Handle creator-based crawling

        Returns:
            None
        """
        await self.get_creators_and_notes()

    def _find_creator_index_in_creator_list(self, creator_url_token: str) -> int:
        """
        Find creator index in creator list

        Args:
            creator_url_token: Creator URL token

        Returns:
            int: creator index, -1 if not found
        """
        for index, user_link in enumerate(config.ZHIHU_CREATOR_URL_LIST):
            url_token = user_link.split("/")[-1]
            if url_token == creator_url_token:
                return index
        return -1

    async def get_creators_and_notes(self) -> None:
        """
        Get creator's information and their notes and comments

        Returns:
            None
        """
        utils.logger.info(
            "[CreatorHandler.get_creators_and_notes] Begin get zhihu creators"
        )

        creator_list = config.ZHIHU_CREATOR_URL_LIST

        # Initialize checkpoint
        checkpoint = Checkpoint(
            platform=constant.ZHIHU_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_CREATOR,
        )

        # Load checkpoint if enabled
        if config.ENABLE_CHECKPOINT:
            latest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.ZHIHU_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_CREATOR,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if latest_checkpoint:
                checkpoint = latest_checkpoint
                creator_index = self._find_creator_index_in_creator_list(
                    latest_checkpoint.current_creator_id
                )
                if creator_index == -1:
                    utils.logger.warning(
                        f"[CreatorHandler.get_creators_and_notes] Creator {latest_checkpoint.current_creator_id} not found"
                    )
                    creator_index = 0
                else:
                    utils.logger.info(
                        f"[CreatorHandler.get_creators_and_notes] Load checkpoint: {latest_checkpoint.id}"
                    )
                    creator_list = creator_list[creator_index:]

        for user_link in creator_list:
            url_token = user_link.split("/")[-1]

            # Update checkpoint with current creator
            if checkpoint.current_creator_id != url_token:
                # Reset page when switching to a new creator
                checkpoint.current_creator_page = "0"

            checkpoint.current_creator_id = url_token
            await self.checkpoint_manager.save_checkpoint(checkpoint)

            utils.logger.info(
                f"[CreatorHandler.get_creators_and_notes] Begin get creator {url_token}"
            )

            # Get creator detail info
            creator_info: Optional[ZhihuCreator] = await self.zhihu_client.get_creator_info(
                url_token=url_token
            )
            if not creator_info:
                utils.logger.warning(
                    f"[CreatorHandler.get_creators_and_notes] Creator {url_token} not found"
                )
                continue

            utils.logger.info(
                f"[CreatorHandler.get_creators_and_notes] Creator info: {creator_info.user_nickname}"
            )
            await zhihu_store.save_creator(creator=creator_info)

            # Get all answers by creator (only answers as per user requirement)
            all_content_list = await self._get_all_answers_by_creator(
                creator=creator_info,
                checkpoint=checkpoint,
            )

            # Get comments for all contents
            await self.comment_processor.batch_get_content_comments(
                content_list=all_content_list,
                checkpoint_id=checkpoint.id,
            )

        utils.logger.info(
            "[CreatorHandler.get_creators_and_notes] Finished getting creators"
        )

    async def _get_all_answers_by_creator(
        self,
        creator: ZhihuCreator,
        checkpoint: Checkpoint,
    ) -> List[ZhihuContent]:
        """
        Get all answers by creator with checkpoint support

        Args:
            creator: ZhihuCreator object
            checkpoint: Checkpoint object

        Returns:
            List of ZhihuContent (answers)
        """
        all_contents: List[ZhihuContent] = []

        # Resume from checkpoint offset
        offset = int(checkpoint.current_creator_page or "0")
        limit = 20
        is_end = False
        saved_count = offset  # Count from the resumed offset

        while not is_end and saved_count <= config.CRAWLER_MAX_NOTES_COUNT:
            try:
                res = await self.zhihu_client.get_creator_answers(
                    creator.url_token, offset, limit
                )

                if not res:
                    break

                utils.logger.info(
                    f"[CreatorHandler._get_all_answers_by_creator] Get creator {creator.url_token} answers, offset: {offset}"
                )

                paging_info = res.get("paging", {})
                is_end = paging_info.get("is_end", True)

                contents = self._extractor.extract_content_list_from_creator(
                    res.get("data", [])
                )

                if contents:
                    # Process contents with checkpoint support
                    await self.content_processor.batch_process_contents(
                        content_list=contents,
                        checkpoint_id=checkpoint.id,
                    )
                    all_contents.extend(contents)

                offset += limit
                saved_count += len(contents)

                # Update checkpoint with current offset
                latest_checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(
                    checkpoint.id
                )
                if latest_checkpoint:
                    latest_checkpoint.current_creator_page = str(offset)
                    await self.checkpoint_manager.update_checkpoint(latest_checkpoint)

                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            except Exception as ex:
                utils.logger.error(
                    f"[CreatorHandler._get_all_answers_by_creator] Error: {ex}"
                )
                break

        utils.logger.info(
            f"[CreatorHandler._get_all_answers_by_creator] Got {len(all_contents)} answers for creator {creator.url_token}"
        )

        return all_contents
