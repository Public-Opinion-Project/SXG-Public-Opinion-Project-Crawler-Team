# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/xhs/handlers/homefeed_handler.py
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
from ..field import FeedType
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import XiaoHongShuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.note_processor import NoteProcessor
    from ..processors.comment_processor import CommentProcessor


class HomefeedHandler(BaseHandler):
    """Handles homefeed-based crawling operations"""

    def __init__(
        self,
        xhs_client: "XiaoHongShuClient",
        checkpoint_manager: "CheckpointRepoManager",
        note_processor: "NoteProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize homefeed handler

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
        Handle homefeed-based crawling

        Returns:
            None
        """
        await self.get_homefeed_notes()

    async def get_homefeed_notes(self):
        """
        Get homefeed notes and comments
        Returns:
            None
        """
        utils.logger.info(
            "[HomefeedHandler.get_homefeed_notes] Begin get xiaohongshu homefeed notes"
        )

        # 初始化检查点
        checkpoint = Checkpoint(
            platform=constant.XHS_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_HOMEFEED,
            current_homefeed_cursor="",
            current_homefeed_note_index=0,
        )

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.XHS_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_HOMEFEED,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_notes] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
        await self.checkpoint_manager.save_checkpoint(checkpoint)

        current_cursor = checkpoint.current_homefeed_cursor or ""
        note_index = checkpoint.current_homefeed_note_index or 0
        saved_note_count = 0
        note_num = 18

        while saved_note_count <= config.CRAWLER_MAX_NOTES_COUNT:
            try:
                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_notes] Get homefeed notes, current_cursor: {current_cursor}, note_index: {note_index}, note_num: {note_num}"
                )

                homefeed_notes_res = await self.xhs_client.get_homefeed_notes(
                    category=FeedType.RECOMMEND,
                    cursor=current_cursor,
                    note_index=note_index,
                    note_num=note_num,
                )
                if not homefeed_notes_res:
                    utils.logger.info(
                        f"[HomefeedHandler.get_homefeed_notes] No more content!"
                    )
                    break

                cursor_score = homefeed_notes_res.get("cursor_score", "")
                if not cursor_score:
                    utils.logger.info(
                        f"[HomefeedHandler.get_homefeed_notes] No more content!"
                    )
                    break

                items: List[Dict] = homefeed_notes_res.get("items", [])
                note_items = []

                # 首页推荐的信息流，每次API返回的结果不一样的概率大，就有可能遇到上一次中断保存的帖子列表有未完成爬取的，这里做一个补偿。
                compensation_note_ids = set()
                for note_item in checkpoint.crawled_note_list:
                    if not note_item.is_success_crawled:
                        compensation_note_item = {
                            "note_id": note_item.note_id,
                            "xsec_token": note_item.extra_params_info.get(
                                "xsec_token", ""
                            ),
                            "xsec_source": note_item.extra_params_info.get(
                                "xsec_source", ""
                            ),
                        }
                        note_items.append(compensation_note_item)
                        compensation_note_ids.add(note_item.note_id)

                for post_item in items:
                    if post_item.get("model_type") not in ("rec_query", "hot_query"):
                        note_id = post_item.get("id")
                        if not note_id:
                            continue
                        if note_id not in compensation_note_ids:
                            note_item = {
                                "note_id": note_id,
                                "xsec_token": post_item.get("xsec_token", ""),
                                "xsec_source": "pc_feed",
                            }
                            note_items.append(note_item)

                # 限制爬取数量，避免超过 CRAWLER_MAX_NOTES_COUNT
                remaining_notes = config.CRAWLER_MAX_NOTES_COUNT - saved_note_count
                if remaining_notes <= 0:
                    utils.logger.info(
                        f"[HomefeedHandler.get_homefeed_notes] Reached max notes count: {config.CRAWLER_MAX_NOTES_COUNT}"
                    )
                    break
                note_items = note_items[:remaining_notes]

                note_id_list, xsec_tokens = (
                    await self.note_processor.batch_get_note_list(
                        note_list=note_items, checkpoint_id=checkpoint.id
                    )
                )
                await self.comment_processor.batch_get_note_comments(
                    note_id_list, xsec_tokens, checkpoint_id=checkpoint.id
                )

                saved_note_count += len(note_id_list)
                current_cursor = cursor_score
                note_index += note_num

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            except Exception as ex:
                utils.logger.error(
                    f"[HomefeedHandler.get_homefeed_notes] Get homefeed notes error: {ex}"
                )
                # 发生异常了，则打印当前爬取的游标和索引，用于后续继续爬取
                utils.logger.info(
                    "------------------------------------------记录当前爬取的游标和索引------------------------------------------"
                )
                for i in range(3):
                    utils.logger.error(
                        f"[HomefeedHandler.get_homefeed_notes] Current cursor: {current_cursor}, note_index: {note_index}"
                    )
                utils.logger.info(
                    "------------------------------------------记录当前爬取的游标和索引---------------------------------------------------"
                )

                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_notes] 可以在配置文件中开启断点续爬功能，继续爬取当前位置的信息"
                )
                return

            finally:
                # 更新检查点状态
                lastest_checkpoint = (
                    await self.checkpoint_manager.load_checkpoint_by_id(checkpoint.id)
                )
                lastest_checkpoint.current_homefeed_cursor = current_cursor
                lastest_checkpoint.current_homefeed_note_index = note_index
                await self.checkpoint_manager.update_checkpoint(lastest_checkpoint)

        utils.logger.info(
            "[HomefeedHandler.get_homefeed_notes] XiaoHongShu homefeed notes crawler finished ..."
        )
