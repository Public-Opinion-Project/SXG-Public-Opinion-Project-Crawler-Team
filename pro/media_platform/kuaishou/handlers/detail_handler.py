# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/kuaishou/handlers/detail_handler.py
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
from typing import TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import KuaiShouApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.video_processor import VideoProcessor
    from ..processors.comment_processor import CommentProcessor


class DetailHandler(BaseHandler):
    """Handles detail-based crawling operations for specified videos"""

    def __init__(
        self,
        ks_client: "KuaiShouApiClient",
        checkpoint_manager: "CheckpointRepoManager",
        video_processor: "VideoProcessor",
        comment_processor: "CommentProcessor"
    ):
        """
        Initialize detail handler

        Args:
            ks_client: Kuaishou API client
            checkpoint_manager: Checkpoint manager for resume functionality
            video_processor: Video processing component
            comment_processor: Comment processing component
        """
        super().__init__(ks_client, checkpoint_manager, video_processor, comment_processor)

    async def handle(self) -> None:
        """
        Handle detail-based crawling

        Returns:
            None
        """
        await self.get_specified_videos()

    async def get_specified_videos(self) -> None:
        """
        Get the information and comments of the specified videos with checkpoint support
        Returns:
            None
        """
        utils.logger.info("[DetailHandler.get_specified_videos] Begin get specified videos")
        checkpoint = Checkpoint(platform=constant.KUAISHOU_PLATFORM_NAME, mode=constant.CRALER_TYPE_DETAIL)

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.KUAISHOU_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_DETAIL,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[DetailHandler.get_specified_videos] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
        await self.checkpoint_manager.save_checkpoint(checkpoint)

        # 使用video processor批量处理指定的视频
        processed_video_ids = await self.video_processor.batch_get_video_list(
            config.KS_SPECIFIED_ID_LIST, checkpoint.id
        )

        # 批量获取视频评论
        await self.comment_processor.batch_get_video_comments(processed_video_ids, checkpoint.id)

        # 爬虫请求间隔时间
        await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

        utils.logger.info("[DetailHandler.get_specified_videos] Completed processing specified videos")
