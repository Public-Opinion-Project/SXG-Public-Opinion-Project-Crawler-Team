# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/bilibili/handlers/creator_handler.py
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
from typing import List, Dict, TYPE_CHECKING

import config
import constant
from model.m_bilibili import VideoIdInfo
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from repo.platform_save_data import bilibili as bilibili_store
from .base_handler import BaseHandler
from ..field import SearchOrderType

if TYPE_CHECKING:
    from ..client import BilibiliClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.video_processor import VideoProcessor
    from ..processors.comment_processor import CommentProcessor


class CreatorHandler(BaseHandler):
    """Handles creator-based crawling operations"""

    def __init__(
            self,
            bili_client: "BilibiliClient",
            checkpoint_manager: "CheckpointRepoManager",
            video_processor: "VideoProcessor",
            comment_processor: "CommentProcessor",
    ):
        """
        Initialize creator handler

        Args:
            bili_client: Bilibili API client
            checkpoint_manager: Checkpoint manager for resume functionality
            video_processor: Video processing component
            comment_processor: Comment processing component
        """
        super().__init__(
            bili_client, checkpoint_manager, video_processor, comment_processor
        )

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
        creator_list = config.BILI_CREATOR_ID_LIST
        for index, creator_item in enumerate(creator_list):
            if creator_item == creator_id:
                return index
        return -1

    async def get_creators_and_videos(self) -> None:
        """
        Get creator's information and their videos and comments
        Returns:
            None
        """
        utils.logger.info(
            "[CreatorHandler.get_creators_and_videos] Begin get bilibili creators"
        )
        checkpoint = Checkpoint(
            platform=constant.BILIBILI_PLATFORM_NAME, mode=constant.CRALER_TYPE_CREATOR
        )
        creator_list = config.BILI_CREATOR_ID_LIST

        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.BILIBILI_PLATFORM_NAME,
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

        for creator_id in creator_list:
            checkpoint.current_creator_id = creator_id
            await self.checkpoint_manager.save_checkpoint(checkpoint)

            # 获取创作者信息
            creator_info = await self.bili_client.get_creator_info(creator_id)
            if creator_info:
                utils.logger.info(
                    f"[CreatorHandler.get_creators_and_videos] creator_info: user_id={creator_info.user_id}, nickname={creator_info.nickname}"
                )
                await bilibili_store.update_bilibili_up_info(creator_info)

            utils.logger.info(
                f"[CreatorHandler.get_creators_and_videos] begin get creator_id: {creator_id} videos ..."
            )

            # 获取创作者的所有视频
            await self.get_all_videos_by_creator(
                creator_id, checkpoint_id=checkpoint.id
            )

    async def get_all_videos_by_creator(
            self,
            creator_id: str,
            order_mode: SearchOrderType = SearchOrderType.LAST_PUBLISH,
            checkpoint_id: str = "",
    ):
        """
        获取创作者的所有视频
        Args:
            creator_id: 创作者 ID
            order_mode: 排序方式
            checkpoint_id: 检查点ID
        Returns:

        """
        checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
        if not checkpoint:
            raise Exception(
                f"[CreatorHandler.get_all_videos_by_creator] Get checkpoint error, checkpoint_id: {checkpoint_id}"
            )

        result = []
        page_num = int(checkpoint.current_creator_page or 1)
        page_size = 30
        has_more = True
        saved_creator_count = 0
        while has_more and saved_creator_count <= config.CRAWLER_MAX_NOTES_COUNT:
            utils.logger.info(
                f"[CreatorHandler.get_all_videos_by_creator] begin get creator_id: {creator_id} videos, page_num: {page_num} ..."
            )
            videos_res = await self.bili_client.get_creator_videos(
                creator_id, page_num, page_size, order_mode
            )
            utils.logger.info(
                f"[CreatorHandler.get_all_videos_by_creator] get creator_id: {creator_id} videos, page_num: {page_num} success, count: {len(videos_res.get('list', {}).get('vlist', []))} ..."
            )
            video_list = videos_res.get("list", {}).get("vlist", [])
            result.extend(video_list)
            has_more = videos_res.get("page").get("count") > page_num * page_size
            page_num += 1
            saved_creator_count += len(video_list)

            video_ids: List[VideoIdInfo] = await self.video_processor.batch_get_video_list(
                video_list, checkpoint_id=checkpoint_id
            )
            await self.comment_processor.batch_get_video_comments(
                video_ids, checkpoint_id=checkpoint_id
            )

            # 需要加载最新的检查点，因为在fetch_creator_notes_detail方法中，有对检查点左边
            checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
            checkpoint.current_creator_page = str(page_num)
            await self.checkpoint_manager.update_checkpoint(checkpoint)

            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

        return result
