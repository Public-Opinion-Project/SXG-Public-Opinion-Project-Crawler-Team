# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/xhs/handlers/detail_handler.py
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
from typing import List, TYPE_CHECKING, Dict

import config
import constant
from model.m_checkpoint import Checkpoint
from model.m_xhs import NoteUrlInfo
from pkg.tools import utils
from ..extractor import XiaoHongShuExtractor
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import XiaoHongShuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.note_processor import NoteProcessor
    from ..processors.comment_processor import CommentProcessor


class DetailHandler(BaseHandler):
    """Handles detail-based crawling operations for specified notes"""

    def __init__(
        self,
        xhs_client: "XiaoHongShuClient",
        checkpoint_manager: "CheckpointRepoManager",
        note_processor: "NoteProcessor",
        comment_processor: "CommentProcessor"
    ):
        """
        Initialize detail handler

        Args:
            xhs_client: XiaoHongShu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            note_processor: Note processing component
            comment_processor: Comment processing component
        """
        super().__init__(xhs_client, checkpoint_manager, note_processor, comment_processor)
        self.extractor = XiaoHongShuExtractor()

    async def handle(self) -> None:
        """
        Handle detail-based crawling

        Returns:
            None
        """
        await self.get_specified_notes()

    async def get_specified_notes(self):
        """
        Get the information and comments of the specified post
        must be specified note_id, xsec_source, xsec_token
        Returns:
            None
        """
        utils.logger.info(
            "[DetailHandler.get_specified_notes] Begin get xiaohongshu specified notes"
        )

        checkpoint = Checkpoint(platform=constant.XHS_PLATFORM_NAME, mode=constant.CRALER_TYPE_DETAIL)

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.XHS_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_DETAIL,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[DetailHandler.get_specified_notes] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
        await self.checkpoint_manager.save_checkpoint(checkpoint)

        # 从配置文件中解析指定帖子信息
        note_list: List[Dict] = []
        for full_note_url in config.XHS_SPECIFIED_NOTE_URL_LIST:
            note_url_info: NoteUrlInfo = self.extractor.parse_note_info_from_note_url(full_note_url)
            note_list.append(
                {
                    "note_id": note_url_info.note_id,
                    "xsec_token": note_url_info.xsec_token,
                    "xsec_source": note_url_info.xsec_source,
                }
            )

        note_ids, xsec_tokens = await self.note_processor.batch_get_note_list(note_list, checkpoint_id=checkpoint.id)
        await self.comment_processor.batch_get_note_comments(
            note_ids, xsec_tokens, checkpoint_id=checkpoint.id
        )
