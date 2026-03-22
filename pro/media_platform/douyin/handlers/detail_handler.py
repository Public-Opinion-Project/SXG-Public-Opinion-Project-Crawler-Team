# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/douyin/handlers/detail_handler.py
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

from typing import List, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import DouYinApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.aweme_processor import AwemeProcessor
    from ..processors.comment_processor import CommentProcessor


class DetailHandler(BaseHandler):
    """Handles detail-based crawling operations for specified awemes"""

    def __init__(
        self,
        dy_client: "DouYinApiClient",
        checkpoint_manager: "CheckpointRepoManager",
        aweme_processor: "AwemeProcessor",
        comment_processor: "CommentProcessor"
    ):
        """
        Initialize detail handler

        Args:
            dy_client: Douyin API client
            checkpoint_manager: Checkpoint manager for resume functionality
            aweme_processor: Aweme processing component
            comment_processor: Comment processing component
        """
        super().__init__(dy_client, checkpoint_manager, aweme_processor, comment_processor)

    async def handle(self) -> None:
        """
        Handle detail-based crawling

        Returns:
            None
        """
        await self.get_specified_awemes()

    async def get_specified_awemes(self):
        """
        Get the information and comments of the specified post
        Returns:
            None
        """
        utils.logger.info(
            "[DetailHandler.get_specified_awemes] Begin get douyin specified awemes"
        )

        checkpoint = Checkpoint(platform=constant.DOUYIN_PLATFORM_NAME, mode=constant.CRALER_TYPE_DETAIL)

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.DOUYIN_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_DETAIL,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[DetailHandler.get_specified_awemes] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
        await self.checkpoint_manager.save_checkpoint(checkpoint)

        processed_aweme_ids = await self.aweme_processor.batch_get_aweme_list_from_ids(
            config.DY_SPECIFIED_ID_LIST, checkpoint_id=checkpoint.id
        )
        await self.comment_processor.batch_get_aweme_comments(
            processed_aweme_ids, checkpoint_id=checkpoint.id
        )
