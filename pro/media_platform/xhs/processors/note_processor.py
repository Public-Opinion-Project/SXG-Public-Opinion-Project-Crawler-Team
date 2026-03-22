# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/xhs/processors/note_processor.py
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
from typing import Dict, List, Optional, TYPE_CHECKING, Tuple
from model.m_xhs import XhsNote
from tenacity import RetryError

import config
from pkg.tools import utils
from repo.platform_save_data import xhs as xhs_store
from ..exception import DataFetchError

if TYPE_CHECKING:
    from ..client import XiaoHongShuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class NoteProcessor:
    """Handles note processing operations including detail extraction and batch processing"""

    def __init__(
        self,
        xhs_client: "XiaoHongShuClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_note_task_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize note processor

        Args:
            xhs_client: XiaoHongShu API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_note_task_semaphore: Semaphore to limit concurrent note tasks
        """
        self.xhs_client = xhs_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_note_task_semaphore = crawler_note_task_semaphore

    async def get_note_detail_async_task(
        self,
        note_id: str,
        xsec_source: str,
        xsec_token: str,
        checkpoint_id: str,
    ) -> Optional[XhsNote]:
        """
        Get note detail from html or api

        Args:
            note_id: note id
            xsec_source: xsec source
            xsec_token: xsec token
            checkpoint_id: checkpoint id
        Returns:
            note detail
        """
        note_detail: Optional[XhsNote] = None
        async with self.crawler_note_task_semaphore:
            try:
                note_detail_from_api: Optional[XhsNote] = (
                    await self.xhs_client.get_note_by_id(
                        note_id, xsec_source, xsec_token
                    )
                )

                if not note_detail_from_api:
                    note_detail_from_html: Optional[XhsNote] = (
                        await self.xhs_client.get_note_by_id_from_html(
                            note_id, xsec_source, xsec_token
                        )
                    )

                note_detail = note_detail_from_api or note_detail_from_html
                if note_detail:
                    await xhs_store.update_xhs_note(note_detail)
                    return note_detail

            except DataFetchError as ex:
                utils.logger.error(
                    f"[NoteProcessor.get_note_detail_async_task] Get note detail error: {ex}"
                )
                return None

            except KeyError as ex:
                utils.logger.error(
                    f"[NoteProcessor.get_note_detail_async_task] have not fund note detail note_id:{note_id}, err: {ex}"
                )
                return None

            except RetryError as ex:
                utils.logger.error(
                    f"[NoteProcessor.get_note_detail_async_task] Get note detail error: {ex}"
                )
                return None

            finally:
                is_success_crawled = note_detail is not None
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint_id,
                    note_id=note_id,
                    is_success_crawled=is_success_crawled,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                )

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

    async def batch_get_note_list(
        self, note_list: List[Dict], checkpoint_id: str = ""
    ) -> Tuple[List[str], List[str]]:
        """
        Concurrently obtain the specified post list and save the data
        Args:
            note_list: List of note items
            checkpoint_id: Checkpoint ID

        Returns:
            Tuple of note IDs and xsec tokens
        """
        task_list, note_ids, xsec_tokens = [], [], []
        for note_item in note_list:
            note_id = note_item.get("note_id", "")
            if not note_id:
                continue

            note_ids.append(note_id)
            xsec_tokens.append(note_item.get("xsec_token", ""))

            if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=note_item.get("note_id", "")
            ):
                utils.logger.info(
                    f"[NoteProcessor.batch_get_notes] Note {note_item.get('note_id', '')} is already crawled, skip"
                )
                continue

            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint_id,
                note_id=note_item.get("note_id", ""),
                extra_params_info={
                    "xsec_source": note_item.get("xsec_source", ""),
                    "xsec_token": note_item.get("xsec_token", ""),
                },
            )
            task = self.get_note_detail_async_task(
                note_id=note_item.get("note_id", ""),
                xsec_source=note_item.get("xsec_source", ""),
                xsec_token=note_item.get("xsec_token", ""),
                checkpoint_id=checkpoint_id,
            )
            task_list.append(task)

        await asyncio.gather(*task_list)
        return note_ids, xsec_tokens
