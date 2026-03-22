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
from typing import Dict, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from pkg.tools import utils
from .base_handler import BaseHandler
from ..help import ZhihuExtractor

if TYPE_CHECKING:
    from ..client import ZhiHuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.content_processor import ContentProcessor
    from ..processors.comment_processor import CommentProcessor


class HomefeedHandler(BaseHandler):
    """Handles homefeed-based crawling operations for Zhihu"""

    def __init__(
        self,
        zhihu_client: "ZhiHuClient",
        checkpoint_manager: "CheckpointRepoManager",
        content_processor: "ContentProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize homefeed handler

        Args:
            zhihu_client: Zhihu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            content_processor: Content processing component
            comment_processor: Comment processing component
        """
        super().__init__(
            zhihu_client, checkpoint_manager, content_processor, comment_processor
        )
        self._extractor = ZhihuExtractor()

    async def handle(self) -> None:
        """
        Handle homefeed-based crawling

        Returns:
            None
        """
        await self.get_homefeed_notes()

    def _parse_homefeed_cursor(self, cursor_str: str) -> Dict:
        """
        Parse homefeed cursor string

        Args:
            cursor_str: Cursor string in format "after_id|end_offset|session_token"

        Returns:
            Dict with after_id, end_offset, session_token
        """
        if not cursor_str:
            return {"after_id": 0, "end_offset": 0, "session_token": ""}

        parts = cursor_str.split("|")
        return {
            "after_id": int(parts[0]) if len(parts) > 0 and parts[0] else 0,
            "end_offset": int(parts[1]) if len(parts) > 1 and parts[1] else 0,
            "session_token": parts[2] if len(parts) > 2 else "",
        }

    def _format_homefeed_cursor(
        self, after_id: int, end_offset: int, session_token: str
    ) -> str:
        """
        Format homefeed cursor to string

        Args:
            after_id: After ID
            end_offset: End offset
            session_token: Session token

        Returns:
            Cursor string
        """
        return f"{after_id}|{end_offset}|{session_token}"

    async def get_homefeed_notes(self):
        """
        Get homefeed notes and comments with checkpoint support

        Returns:
            None
        """
        utils.logger.info(
            "[HomefeedHandler.get_homefeed_notes] Begin get zhihu homefeed notes"
        )

        # Initialize checkpoint
        checkpoint = Checkpoint(
            platform=constant.ZHIHU_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_HOMEFEED,
            current_homefeed_cursor="",
            current_homefeed_note_index=1,
        )

        # Load checkpoint if enabled
        if config.ENABLE_CHECKPOINT:
            latest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.ZHIHU_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_HOMEFEED,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if latest_checkpoint:
                checkpoint = latest_checkpoint
                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_notes] Load checkpoint: {latest_checkpoint.id}"
                )

        await self.checkpoint_manager.save_checkpoint(checkpoint)

        # Parse cursor from checkpoint
        cursor_info = self._parse_homefeed_cursor(checkpoint.current_homefeed_cursor)
        after_id = cursor_info["after_id"]
        end_offset = cursor_info["end_offset"]
        session_token = cursor_info["session_token"]
        page_number = checkpoint.current_homefeed_note_index or 1
        saved_count = 0

        while saved_count <= config.CRAWLER_MAX_NOTES_COUNT:
            try:
                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_notes] Get homefeed, page: {page_number}, after_id: {after_id}"
                )

                homefeed_res = await self.zhihu_client.get_homefeed_notes(
                    page_number=page_number,
                    after_id=after_id,
                    end_offset=end_offset,
                    seesion_token=session_token,
                )

                paging_info: Dict = homefeed_res.get("paging", {})
                if not paging_info or paging_info.get("is_end", False):
                    utils.logger.info("No more homefeed notes")
                    break

                content_list = self._extractor.extract_contents_from_homefeed(
                    homefeed_res
                )

                if not content_list:
                    utils.logger.info("No content in homefeed response")
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

                # Extract next request params from URL
                next_params = self._extractor.extract_next_req_params_from_url(
                    paging_info,
                    specific_params=["after_id", "end_offset", "session_token"],
                )

                after_id = int(next_params.get("after_id", 0))
                end_offset = int(next_params.get("end_offset", 0))
                session_token = next_params.get("session_token", "")
                page_number += 1
                saved_count += len(content_ids)

                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_notes] Got {len(content_ids)} contents, total: {saved_count}"
                )

                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            except Exception as ex:
                utils.logger.error(
                    f"[HomefeedHandler.get_homefeed_notes] Error: {ex}"
                )
                break

            finally:
                # Update checkpoint with current cursor
                latest_checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(
                    checkpoint.id
                )
                if latest_checkpoint:
                    latest_checkpoint.current_homefeed_cursor = self._format_homefeed_cursor(
                        after_id, end_offset, session_token
                    )
                    latest_checkpoint.current_homefeed_note_index = page_number
                    await self.checkpoint_manager.update_checkpoint(latest_checkpoint)

        utils.logger.info(
            f"[HomefeedHandler.get_homefeed_notes] Finished, total saved: {saved_count}"
        )
