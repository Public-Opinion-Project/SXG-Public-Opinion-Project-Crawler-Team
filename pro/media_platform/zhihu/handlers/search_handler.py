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
from typing import List, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from var import source_keyword_var
from .base_handler import BaseHandler
from ..exception import DataFetchError

if TYPE_CHECKING:
    from ..client import ZhiHuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.content_processor import ContentProcessor
    from ..processors.comment_processor import CommentProcessor


class SearchHandler(BaseHandler):
    """Handles search-based crawling operations for Zhihu"""

    def __init__(
        self,
        zhihu_client: "ZhiHuClient",
        checkpoint_manager: "CheckpointRepoManager",
        content_processor: "ContentProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize search handler

        Args:
            zhihu_client: Zhihu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            content_processor: Content processing component
            comment_processor: Comment processing component
        """
        super().__init__(
            zhihu_client, checkpoint_manager, content_processor, comment_processor
        )

    async def handle(self) -> None:
        """
        Handle search-based crawling

        Returns:
            None
        """
        await self.search()

    @staticmethod
    def _get_search_keyword_list() -> List[str]:
        """
        Get search keyword list

        Returns:
            List[str]: search keyword list
        """
        return config.KEYWORDS.split(",")

    def _find_keyword_index_in_keyword_list(self, keyword: str) -> int:
        """
        Find keyword index in keyword list

        Args:
            keyword: keyword

        Returns:
            int: keyword index
        """
        keyword_list = self._get_search_keyword_list()
        for index, keyword_item in enumerate(keyword_list):
            if keyword_item == keyword:
                return index
        return -1

    async def search(self) -> None:
        """
        Search for zhihu contents and retrieve their comment information.

        Returns:
            None
        """
        utils.logger.info("[SearchHandler.search] Begin search zhihu keywords")
        zhihu_limit_count = 20  # zhihu limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < zhihu_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = zhihu_limit_count

        keyword_list = self._get_search_keyword_list()
        start_page = config.START_PAGE

        # Initialize checkpoint
        checkpoint = Checkpoint(
            platform=constant.ZHIHU_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_SEARCH,
            current_search_page=start_page,
        )

        # Load checkpoint if enabled
        if config.ENABLE_CHECKPOINT:
            latest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.ZHIHU_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_SEARCH,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if latest_checkpoint:
                keyword_index = self._find_keyword_index_in_keyword_list(
                    latest_checkpoint.current_search_keyword
                )
                if keyword_index == -1:
                    # Keyword not found, start from the first keyword
                    utils.logger.warning(
                        f"[SearchHandler.search] Keyword {latest_checkpoint.current_search_keyword} not found in keyword list"
                    )
                    keyword_index = 0
                else:
                    # Resume from the checkpoint
                    checkpoint = latest_checkpoint
                    utils.logger.info(
                        f"[SearchHandler.search] Load checkpoint: {latest_checkpoint.id}"
                    )
                    keyword_list = keyword_list[keyword_index:]

        for keyword in keyword_list:
            source_keyword_var.set(keyword)
            page = checkpoint.current_search_page or start_page

            # Reset page when switching to a new keyword
            if checkpoint.current_search_keyword != keyword:
                page = start_page

            # Save checkpoint with current keyword
            checkpoint.current_search_keyword = keyword
            await self.checkpoint_manager.save_checkpoint(checkpoint)

            utils.logger.info(
                f"[SearchHandler.search] Current search keyword: {keyword}"
            )

            saved_note_count = (page - start_page) * zhihu_limit_count

            while saved_note_count <= config.CRAWLER_MAX_NOTES_COUNT:
                try:
                    utils.logger.info(
                        f"[SearchHandler.search] search zhihu keyword: {keyword}, page: {page}"
                    )
                    content_list = await self.zhihu_client.get_note_by_keyword(
                        keyword=keyword,
                        page=page,
                    )
                    utils.logger.info(
                        f"[SearchHandler.search] Search contents count: {len(content_list)}"
                    )

                    if not content_list:
                        utils.logger.info("No more content!")
                        break

                    # Process contents with checkpoint support
                    content_ids = await self.content_processor.batch_process_contents(
                        content_list=content_list,
                        checkpoint_id=checkpoint.id,
                    )

                    # Get comments for contents
                    await self.comment_processor.batch_get_content_comments(
                        content_list=content_list,
                        checkpoint_id=checkpoint.id,
                    )

                    page += 1
                    saved_note_count += len(content_ids)

                    # Crawler request interval
                    await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

                except DataFetchError:
                    utils.logger.error("[SearchHandler.search] Search content error")
                    return

                except Exception as ex:
                    utils.logger.error(
                        f"[SearchHandler.search] Search notes error: {ex}"
                    )
                    # Log current progress for manual recovery
                    utils.logger.info(
                        "------------------------------------------ Record current keyword and page ------------------------------------------"
                    )
                    for _ in range(3):
                        utils.logger.error(
                            f"[SearchHandler.search] Current keyword: {keyword}, page: {page}"
                        )
                    utils.logger.info(
                        "------------------------------------------ Record current keyword and page ------------------------------------------"
                    )
                    utils.logger.info(
                        f"[SearchHandler.search] You can enable checkpoint mode in config to resume crawling"
                    )
                    return

                finally:
                    # Update checkpoint with current page
                    latest_checkpoint = (
                        await self.checkpoint_manager.load_checkpoint_by_id(
                            checkpoint.id
                        )
                    )
                    if latest_checkpoint:
                        latest_checkpoint.current_search_page = page
                        await self.checkpoint_manager.update_checkpoint(
                            latest_checkpoint
                        )
