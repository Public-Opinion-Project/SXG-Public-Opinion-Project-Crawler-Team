# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/douyin/handlers/search_handler.py
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
from typing import Dict, List, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from repo.platform_save_data import douyin as douyin_store
from var import source_keyword_var
from ..field import PublishTimeType
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import DouYinApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.aweme_processor import AwemeProcessor
    from ..processors.comment_processor import CommentProcessor


class SearchHandler(BaseHandler):
    """Handles search-based crawling operations"""

    def __init__(
        self,
        dy_client: "DouYinApiClient",
        checkpoint_manager: "CheckpointRepoManager",
        aweme_processor: "AwemeProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize search handler

        Args:
            dy_client: Douyin API client
            checkpoint_manager: Checkpoint manager for resume functionality
            aweme_processor: Aweme processing component
            comment_processor: Comment processing component
        """
        super().__init__(
            dy_client, checkpoint_manager, aweme_processor, comment_processor
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
        Search for video list and retrieve their comment information.
        Returns:
            None
        """
        utils.logger.info("[SearchHandler.search] Begin search douyin keywords")
        dy_limit_count = 20  # douyin limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < dy_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = dy_limit_count

        keyword_list = self._get_search_keyword_list()
        checkpoint = Checkpoint(
            platform=constant.DOUYIN_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_SEARCH,
            current_search_page=1,
        )

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.DOUYIN_PLATFORM_NAME,
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
            page = checkpoint.current_search_page
            dy_search_id = checkpoint.current_search_id or ""

            # bugfix: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/issues/311
            if checkpoint.current_search_keyword != keyword:
                page = 1
                dy_search_id = ""

            # 按关键字保存检查点，后面的业务行为都是基于这个检查点来更新page信息，所以需要先保存检查点
            checkpoint.current_search_keyword = keyword
            await self.checkpoint_manager.save_checkpoint(checkpoint)
            saved_aweme_count = (page - 1) * dy_limit_count
            utils.logger.info(f"[SearchHandler.search] Current keyword: {keyword}")

            while saved_aweme_count <= config.CRAWLER_MAX_NOTES_COUNT:
                try:
                    utils.logger.info(
                        f"[SearchHandler.search] search douyin keyword: {keyword}, page: {page}"
                    )
                    posts_res = await self.dy_client.search_info_by_keyword(
                        keyword=keyword,
                        offset=(page - 1) * dy_limit_count,
                        publish_time=PublishTimeType(config.PUBLISH_TIME_TYPE),
                        search_id=dy_search_id,
                    )

                    if "data" not in posts_res:
                        utils.logger.error(
                            f"[SearchHandler.search] search douyin keyword: {keyword} failed，账号也许被风控了。"
                        )
                        break

                    dy_search_id = posts_res.get("extra", {}).get("logid", "")
                    aweme_id_list: List[str] = []

                    post_item_list: List[Dict] = posts_res.get("data")
                    if len(post_item_list) == 0:
                        utils.logger.error(
                            f"[SearchHandler.search] search douyin keyword: {keyword} empty post list。"
                        )
                        break

                    for post_item in post_item_list:
                        try:
                            aweme_info: Dict = (
                                post_item.get("aweme_info")
                                or post_item.get("aweme_mix_info", {}).get("mix_items")[
                                    0
                                ]
                            )
                        except TypeError:
                            continue

                        aweme_id = aweme_info.get("aweme_id", "")
                        if not aweme_id:
                            continue

                        aweme_id_list.append(aweme_id)

                        # 检查是否已经爬取过
                        if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                            checkpoint_id=checkpoint.id, note_id=aweme_id
                        ):
                            utils.logger.info(
                                f"[SearchHandler.search] Aweme {aweme_id} is already crawled, skip"
                            )
                            saved_aweme_count += 1
                            continue

                        await self.checkpoint_manager.add_note_to_checkpoint(
                            checkpoint_id=checkpoint.id,
                            note_id=aweme_id,
                            extra_params_info={},
                            is_success_crawled=True,
                        )

                        from media_platform.douyin.extractor import DouyinExtractor
                        extractor = DouyinExtractor()
                        aweme = extractor.extract_aweme_from_dict(aweme_info)
                        if aweme:
                            await douyin_store.update_douyin_aweme(aweme_item=aweme)
                        saved_aweme_count += 1

                    utils.logger.info(
                        f"[SearchHandler.search] keyword:{keyword}, aweme_id_list:{aweme_id_list}"
                    )
                    await self.comment_processor.batch_get_aweme_comments(
                        aweme_id_list, checkpoint_id=checkpoint.id
                    )

                    page += 1

                    # 爬虫请求间隔时间
                    await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

                except Exception as ex:
                    utils.logger.error(
                        f"[SearchHandler.search] Search videos error: {ex}"
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
                        lastest_checkpoint.current_search_id = dy_search_id
                        await self.checkpoint_manager.update_checkpoint(
                            lastest_checkpoint
                        )
