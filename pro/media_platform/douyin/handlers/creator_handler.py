# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/douyin/handlers/creator_handler.py
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
from typing import Dict, List, TYPE_CHECKING, Optional, Callable

import config
import constant
from model.m_checkpoint import Checkpoint
from model.m_douyin import DouyinAweme
from pkg.tools import utils
from repo.platform_save_data import douyin as douyin_store
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import DouYinApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.aweme_processor import AwemeProcessor
    from ..processors.comment_processor import CommentProcessor


class CreatorHandler(BaseHandler):
    """Handles creator-based crawling operations"""

    def __init__(
            self,
            dy_client: "DouYinApiClient",
            checkpoint_manager: "CheckpointRepoManager",
            aweme_processor: "AwemeProcessor",
            comment_processor: "CommentProcessor"
    ):
        """
        Initialize creator handler

        Args:
            dy_client: Douyin API client
            checkpoint_manager: Checkpoint manager for resume functionality
            aweme_processor: Aweme processing component
            comment_processor: Comment processing component
        """
        super().__init__(dy_client, checkpoint_manager, aweme_processor, comment_processor)

    async def handle(self) -> None:
        """
        Handle creator-based crawling

        Returns:
            None
        """
        await self.get_creators_and_videos()

    @staticmethod
    def _find_creator_index_in_creator_list(creator_id: str) -> int:
        """
        Find creator index in creator list

        Args:
            creator_id: creator id

        Returns:
            int: creator index
        """
        creator_list = config.DY_CREATOR_ID_LIST
        for index, creator_item in enumerate(creator_list):
            if creator_item == creator_id:
                return index
        return -1

    async def get_creators_and_videos(self) -> None:
        """
        Get the information and videos of the specified creator
        Returns:
            None
        """
        utils.logger.info(
            "[CreatorHandler.get_creators_and_videos] Begin get douyin creators"
        )
        checkpoint = Checkpoint(platform=constant.DOUYIN_PLATFORM_NAME, mode=constant.CRALER_TYPE_CREATOR)
        creator_list = config.DY_CREATOR_ID_LIST

        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.DOUYIN_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_CREATOR,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[CreatorHandler.get_creators_and_videos] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
                creator_index = self._find_creator_index_in_creator_list(
                    lastest_checkpoint.current_creator_id
                )
                if creator_index == -1:
                    utils.logger.error(
                        f"[CreatorHandler.get_creators_and_videos] Creator {lastest_checkpoint.current_creator_id} not found in creator list"
                    )
                    creator_index = 0

                creator_list = creator_list[creator_index:]

        for user_id in creator_list:
            checkpoint.current_creator_id = user_id
            await self.checkpoint_manager.save_checkpoint(checkpoint)

            creator = await self.dy_client.get_user_info(user_id)
            if creator:
                await douyin_store.save_creator(user_id, creator=creator)

            await self.get_all_user_aweme_posts(
                sec_user_id=user_id,
                checkpoint_id=checkpoint.id
            )

    async def get_all_user_aweme_posts(
            self,
            sec_user_id: str,
            checkpoint_id: str = ""
    ):
        """
        获取指定用户的所有视频
        Args:
            sec_user_id: 用户ID
            checkpoint_id: 检查点ID

        Returns:
            List of aweme posts
        """
        checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
        if not checkpoint:
            raise Exception(
                f"[CreatorHandler.get_all_notes_by_creator] Get checkpoint error, checkpoint_id: {checkpoint_id}"
            )

        posts_has_more = 1
        max_cursor = checkpoint.current_creator_page or "0"
        result = []
        while posts_has_more == 1 and len(result) <= config.CRAWLER_MAX_NOTES_COUNT:
            aweme_post_res = await self.dy_client.get_user_aweme_posts(sec_user_id, max_cursor)
            posts_has_more = aweme_post_res.get("has_more", 0)
            max_cursor = aweme_post_res.get("max_cursor")
            aweme_list = (
                aweme_post_res.get("aweme_list")
                if aweme_post_res.get("aweme_list")
                else []
            )
            if not aweme_list:
                # 如果获取到的视频列表为空，则认为该用户没有视频，直接跳出循环 还有一种可能是私密账号
                utils.logger.info(
                    f"[AwemeProcessor.get_all_user_aweme_posts] sec_user_id:{sec_user_id} has no video"
                )
                break

            utils.logger.info(
                f"[AwemeProcessor.get_all_user_aweme_posts] got sec_user_id:{sec_user_id} creator page cursor: {max_cursor}"
            )

            aweme_ids = []
            for aweme_info in aweme_list:
                aweme_id = aweme_info.get("aweme_id", "")
                if not aweme_id:
                    continue

                aweme_ids.append(aweme_id)

                # 检查是否已经爬取过
                if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                        checkpoint_id=checkpoint.id, note_id=aweme_id
                ):
                    utils.logger.info(
                        f"[SearchHandler.search] Aweme {aweme_id} is already crawled, skip"
                    )
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

            await self.comment_processor.batch_get_aweme_comments(
                aweme_ids, checkpoint_id=checkpoint_id
            )
            result.extend(aweme_list)

            # 需要加载最新的检查点，因为在fetch_creator_notes_detail方法中，有对检查点左边
            checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
            checkpoint.current_creator_page = str(max_cursor)
            await self.checkpoint_manager.update_checkpoint(checkpoint)

            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

        return result
