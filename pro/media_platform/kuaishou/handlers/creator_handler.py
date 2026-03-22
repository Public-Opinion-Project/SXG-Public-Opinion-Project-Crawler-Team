# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/kuaishou/handlers/creator_handler.py
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
from typing import Dict, List, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from repo.platform_save_data import kuaishou as kuaishou_store
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import KuaiShouApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.video_processor import VideoProcessor
    from ..processors.comment_processor import CommentProcessor


class CreatorHandler(BaseHandler):
    """Handles creator-based crawling operations for specified creators"""

    def __init__(
        self,
        ks_client: "KuaiShouApiClient",
        checkpoint_manager: "CheckpointRepoManager",
        video_processor: "VideoProcessor",
        comment_processor: "CommentProcessor"
    ):
        """
        Initialize creator handler

        Args:
            ks_client: Kuaishou API client
            checkpoint_manager: Checkpoint manager for resume functionality
            video_processor: Video processing component
            comment_processor: Comment processing component
        """
        super().__init__(ks_client, checkpoint_manager, video_processor, comment_processor)

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
        creator_list = config.KS_CREATOR_ID_LIST
        for index, creator_item in enumerate(creator_list):
            if creator_item == creator_id:
                return index
        return -1

    async def get_creators_and_videos(self) -> None:
        """
        Get the information and videos of the specified creators
        Returns:
            None
        """
        utils.logger.info(
            "[CreatorHandler.get_creators_and_videos] Begin get kuaishou creators"
        )
        checkpoint = Checkpoint(platform=constant.KUAISHOU_PLATFORM_NAME, mode=constant.CRALER_TYPE_CREATOR)
        creator_list = config.KS_CREATOR_ID_LIST

        if config.ENABLE_CHECKPOINT:
            latest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.KUAISHOU_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_CREATOR,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if latest_checkpoint:
                checkpoint = latest_checkpoint
                utils.logger.info(
                    f"[CreatorHandler.get_creators_and_videos] Load latest checkpoint: {latest_checkpoint.id}"
                )
                creator_index = self._find_creator_index_in_creator_list(
                    latest_checkpoint.current_creator_id
                )
                if creator_index == -1:
                    utils.logger.error(
                        f"[CreatorHandler.get_creators_and_videos] Creator {latest_checkpoint.current_creator_id} not found in creator list"
                    )
                    creator_index = 0

                creator_list = creator_list[creator_index:]

        for user_id in creator_list:
            checkpoint.current_creator_id = user_id
            await self.checkpoint_manager.save_checkpoint(checkpoint)

            # get creator detail info from web html content
            creator_info: Dict = await self.ks_client.get_creator_info(user_id=user_id)
            if not creator_info:
                utils.logger.error(
                    f"[CreatorHandler.get_creators_and_videos] get creator: {user_id} info error: {creator_info}"
                )
                continue

            await kuaishou_store.save_creator(user_id, creator=creator_info)

            await self.get_all_user_videos(
                user_id=user_id,
                checkpoint_id=checkpoint.id
            )

            utils.logger.info(
                f"[CreatorHandler.get_creators_and_videos] Completed processing creator: {user_id}"
            )

    async def get_all_user_videos(
        self,
        user_id: str,
        checkpoint_id: str = ""
    ):
        """
        获取指定用户的所有视频
        Args:
            user_id: 用户ID
            checkpoint_id: 检查点ID

        Returns:
            List of video posts
        """
        checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
        if not checkpoint:
            raise Exception(
                f"[CreatorHandler.get_all_user_videos] Get checkpoint error, checkpoint_id: {checkpoint_id}"
            )

        result = []
        pcursor = checkpoint.current_creator_page or ""
        saved_video_count = 0

        while saved_video_count <= config.CRAWLER_MAX_NOTES_COUNT:
            videos_res = await self.ks_client.get_video_by_creater(user_id, pcursor)
            if not videos_res:
                utils.logger.error(
                    f"[CreatorHandler.get_all_user_videos] The current creator may have been banned by ks, so they cannot access the data."
                )
                break

            vision_profile_photo_list = videos_res.get("visionProfilePhotoList", {})
            pcursor = vision_profile_photo_list.get("pcursor", "")

            videos = vision_profile_photo_list.get("feeds", [])
            if not videos:
                utils.logger.info(
                    f"[CreatorHandler.get_all_user_videos] user_id:{user_id} has no more videos"
                )
                break

            utils.logger.info(
                f"[CreatorHandler.get_all_user_videos] got user_id:{user_id} videos len : {len(videos)}, pcursor: {pcursor}"
            )

            video_ids = []
            for video_info in videos:
                video_id = video_info.get("photo", {}).get("id", "")
                if not video_id:
                    continue

                video_ids.append(video_id)

                # 检查是否已经爬取过
                if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                    checkpoint_id=checkpoint.id, note_id=video_id
                ):
                    utils.logger.info(
                        f"[CreatorHandler.get_all_user_videos] Video {video_id} is already crawled, skip"
                    )
                    saved_video_count += 1
                    continue

                await self.checkpoint_manager.add_note_to_checkpoint(
                    checkpoint_id=checkpoint.id,
                    note_id=video_id,
                    extra_params_info={},
                    is_success_crawled=True,
                )
                video_item = self.ks_client._extractor.extract_video_from_dict(video_info)
                if video_item:
                    await kuaishou_store.update_kuaishou_video(video_item=video_item)
                saved_video_count += 1

            await self.comment_processor.batch_get_video_comments(
                video_ids, checkpoint_id=checkpoint_id
            )
            result.extend(videos)

            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            # 需要加载最新的检查点，因为在处理过程中，有对检查点的更新
            checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
            checkpoint.current_creator_page = pcursor
            await self.checkpoint_manager.update_checkpoint(checkpoint)

            if pcursor == "no_more":
                break

        return result
