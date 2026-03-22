# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/bilibili/handlers/homefeed_handler.py
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
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import BilibiliClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.video_processor import VideoProcessor
    from ..processors.comment_processor import CommentProcessor


class HomefeedHandler(BaseHandler):
    """Handles homefeed-based crawling operations"""

    def __init__(
        self,
        bili_client: "BilibiliClient",
        checkpoint_manager: "CheckpointRepoManager",
        video_processor: "VideoProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize homefeed handler

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
        Handle homefeed-based crawling

        Returns:
            None
        """
        await self.get_homefeed_videos()

    async def get_homefeed_videos(self):
        """
        Get homefeed videos and comments with checkpoint support
        """
        utils.logger.info(
            "[HomefeedHandler.get_homefeed_videos] Begin get bilibili homefeed videos"
        )

        checkpoint = Checkpoint(
            platform=constant.BILIBILI_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_HOMEFEED,
            current_homefeed_note_index=1,
        )

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.BILIBILI_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_HOMEFEED,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_videos] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
        await self.checkpoint_manager.save_checkpoint(checkpoint)

        per_page_count = 12
        current_page_idx = checkpoint.current_homefeed_note_index or 1
        save_video_count = (current_page_idx - 1) * per_page_count
        while save_video_count <= config.CRAWLER_MAX_NOTES_COUNT:
            try:
                homefeed_videos_res = await self.bili_client.get_homefeed_videos(
                    page_count=per_page_count, fresh_idx=current_page_idx
                )
                videos_list: List[Dict] = homefeed_videos_res.get("item", [])
                if not videos_list:
                    utils.logger.info(
                        f"[HomefeedHandler.get_homefeed_videos] No more content!"
                    )
                    break

                # goto: 目标类型，av: 视频 ogv: 边栏 live: 直播
                # show_info: 展示信息: 1: 普通视频 0: 直播
                filtered_video_list = [
                    video
                    for video in videos_list
                    if video.get("goto") == "av" and video.get("show_info") == 1
                ]

                # 限制爬取数量，避免超过 CRAWLER_MAX_NOTES_COUNT
                remaining_videos = config.CRAWLER_MAX_NOTES_COUNT - save_video_count
                if remaining_videos <= 0:
                    utils.logger.info(
                        f"[HomefeedHandler.get_homefeed_videos] Reached max videos count: {config.CRAWLER_MAX_NOTES_COUNT}"
                    )
                    break
                filtered_video_list = filtered_video_list[:remaining_videos]

                video_infos: List[VideoIdInfo] = await self.video_processor.batch_get_video_list(
                    filtered_video_list, checkpoint_id=checkpoint.id
                )
                await self.comment_processor.batch_get_video_comments(
                    video_infos, checkpoint_id=checkpoint.id
                )

                current_page_idx += 1
                save_video_count += len(video_infos)
                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_videos] Get homefeed videos, current_page_idx: {current_page_idx}, per_page_count: {per_page_count}, save_video_count: {save_video_count}"
                )

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            except Exception as ex:
                utils.logger.error(
                    f"[HomefeedHandler.get_homefeed_videos] Get homefeed videos error: {ex}"
                )
                return

            finally:
                # 更新检查点
                lastest_checkpoint = (
                    await self.checkpoint_manager.load_checkpoint_by_id(checkpoint.id)
                )
                if lastest_checkpoint:
                    lastest_checkpoint.current_homefeed_note_index = current_page_idx
                    await self.checkpoint_manager.update_checkpoint(lastest_checkpoint)

        utils.logger.info(
            "[HomefeedHandler.get_homefeed_videos] Bilibili homefeed videos crawler finished ..."
        )
