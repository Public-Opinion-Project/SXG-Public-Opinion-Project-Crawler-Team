# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/xhs/handlers/search_handler.py
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
from typing import List, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from var import source_keyword_var
from ..field import SearchSortType
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import XiaoHongShuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.note_processor import NoteProcessor
    from ..processors.comment_processor import CommentProcessor


class SearchHandler(BaseHandler):
    """Handles search-based crawling operations"""

    def __init__(
        self,
        xhs_client: "XiaoHongShuClient",
        checkpoint_manager: "CheckpointRepoManager",
        note_processor: "NoteProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize search handler

        Args:
            xhs_client: XiaoHongShu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            note_processor: Note processing component
            comment_processor: Comment processing component
        """
        super().__init__(
            xhs_client, checkpoint_manager, note_processor, comment_processor
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
        Search for notes and retrieve their comment information.
        Returns:
            None
        """
        utils.logger.info("[SearchHandler.search] Begin search xiaohongshu keywords")
        keyword_list = self._get_search_keyword_list()
        checkpoint = Checkpoint(
            platform=constant.XHS_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_SEARCH,
            current_search_page=1,
        )

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.XHS_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_SEARCH,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                keyword_index = self._find_keyword_index_in_keyword_list(
                    lastest_checkpoint.current_search_keyword
                )
                if keyword_index == -1:
                    # 没有搜索到，则从第一个关键词开始爬取
                    utils.logger.warning(
                        f"[SearchHandler.search] Keyword {lastest_checkpoint.current_search_keyword} not found in keyword list"
                    )
                    keyword_index = 0
                else:
                    # 如果搜索到了，则从检查点中保存的当前关键词开始爬取
                    checkpoint = lastest_checkpoint
                    utils.logger.info(
                        f"[SearchHandler.search] Load lastest checkpoint: {lastest_checkpoint.id}"
                    )
                    keyword_list = keyword_list[keyword_index:]

        for keyword in keyword_list:
            source_keyword_var.set(keyword)
            page = checkpoint.current_search_page or 1

            # bugfix: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/issues/311
            if checkpoint.current_search_keyword != keyword:
                page = 1

            # 按关键字保存检查点，后面的业务行为都是基于这个检查点来更新page信息，所以需要先保存检查点
            checkpoint.current_search_keyword = keyword
            await self.checkpoint_manager.save_checkpoint(checkpoint)

            utils.logger.info(
                f"[SearchHandler.search] Current search keyword: {keyword}"
            )

            saved_note_count = (page - 1) * 20
            while saved_note_count <= config.CRAWLER_MAX_NOTES_COUNT:
                try:
                    utils.logger.info(
                        f"[SearchHandler.search] search xhs keyword: {keyword}, page: {page}"
                    )
                    notes_res = await self.xhs_client.get_note_by_keyword(
                        keyword=keyword,
                        page=page,
                        sort=(
                            SearchSortType(config.SORT_TYPE)
                            if config.SORT_TYPE != ""
                            else SearchSortType.GENERAL
                        ),
                    )
                    utils.logger.info(
                        f"[SearchHandler.search] Search notes res count:{len(notes_res.get('items', []))}"
                    )
                    if not notes_res or not notes_res.get("has_more", False):
                        utils.logger.info("No more content!")
                        break

                    # 过滤掉推荐和热门的查询
                    note_list = []
                    for post_item in notes_res.get("items", []):
                        if post_item.get("model_type") in ("rec_query", "hot_query"):
                            continue
                        # 适配 batch_get_note_list
                        post_item["note_id"] = post_item.get("id")
                        note_list.append(post_item)

                    # 限制爬取数量，避免超过 CRAWLER_MAX_NOTES_COUNT
                    remaining_notes = config.CRAWLER_MAX_NOTES_COUNT - saved_note_count
                    if remaining_notes <= 0:
                        utils.logger.info(
                            f"[SearchHandler.search] Reached max notes count: {config.CRAWLER_MAX_NOTES_COUNT}"
                        )
                        break
                    note_list = note_list[:remaining_notes]

                    note_id_list, xsec_tokens = (
                        await self.note_processor.batch_get_note_list(
                            note_list=note_list, checkpoint_id=checkpoint.id
                        )
                    )
                    await self.comment_processor.batch_get_note_comments(
                        note_id_list, xsec_tokens, checkpoint_id=checkpoint.id
                    )

                    page += 1
                    saved_note_count += len(note_id_list)

                    # 爬虫请求间隔时间
                    await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

                except Exception as ex:
                    utils.logger.error(
                        f"[SearchHandler.search] Search notes error: {ex}"
                    )
                    # 发生异常了，则打印当前爬取的关键词和页码，用于后续继续爬取
                    utils.logger.info(
                        "------------------------------------------记录当前爬取的关键词和页码------------------------------------------"
                    )
                    for i in range(3):
                        utils.logger.error(
                            f"[SearchHandler.search] Current keyword: {keyword}, page: {page}"
                        )
                    utils.logger.info(
                        "------------------------------------------记录当前爬取的关键词和页码---------------------------------------------------"
                    )

                    utils.logger.info(
                        f"[SearchHandler.search] 可以在配置文件中开启断点续爬功能，继续爬取当前关键词的信息"
                    )
                    return

                finally:
                    lastest_checkpoint = (
                        await self.checkpoint_manager.load_checkpoint_by_id(
                            checkpoint.id
                        )
                    )
                    if lastest_checkpoint:
                        lastest_checkpoint.current_search_page = page
                        await self.checkpoint_manager.update_checkpoint(
                            lastest_checkpoint
                        )
