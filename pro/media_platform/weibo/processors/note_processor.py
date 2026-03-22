# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/weibo/processors/note_processor.py
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
from typing import List, Optional, TYPE_CHECKING

from pkg.tools import utils
from repo.platform_save_data import weibo as weibo_store
from ..exception import DataFetchError
from config import base_config as config
from model.m_weibo import WeiboNote

if TYPE_CHECKING:
    from ..client import WeiboClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class NoteProcessor:
    """Handles note processing operations including detail extraction and batch processing"""

    def __init__(
        self,
        wb_client: "WeiboClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_note_task_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize note processor

        Args:
            wb_client: Weibo API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_note_task_semaphore: Semaphore to limit concurrent note tasks
        """
        self.wb_client = wb_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_note_task_semaphore = crawler_note_task_semaphore

    async def get_note_detail_async_task(
        self,
        note_id: str,
        checkpoint_id: str,
    ) -> Optional[WeiboNote]:
        """
        Get note detail from API

        Args:
            note_id: note id
            checkpoint_id: checkpoint id
        Returns:
            note detail
        """
        note_detail = None
        async with self.crawler_note_task_semaphore:
            try:
                note_detail = await self.wb_client.get_note_info_by_id(note_id)
                if note_detail:
                    await weibo_store.update_weibo_note(note_detail)
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

            finally:
                is_success_crawled = note_detail is not None
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint_id,
                    note_id=note_id,
                    is_success_crawled=is_success_crawled,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                )

    async def batch_get_note_list(
        self, note_list: List[WeiboNote], checkpoint_id: str = ""
    ) -> List[str]:
        """
        Concurrently obtain the specified post list and save the data
        Args:
            note_list: List of WeiboNote models
            checkpoint_id: Checkpoint ID

        Returns:
            List of note IDs
        """
        note_ids = []
        for note_item in note_list:
            note_id = note_item.note_id
            if not note_id:
                continue

            note_ids.append(note_id)

            if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=note_id
            ):
                utils.logger.info(
                    f"[NoteProcessor.batch_get_note_list] Note {note_id} is already crawled, skip"
                )
                continue

            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint_id,
                note_id=note_id,
                extra_params_info={},
            )

            if config.ENABLE_WEIBO_FULL_TEXT:
                note_detail = await self.get_note_detail_async_task(
                    note_id, checkpoint_id
                )
                if not note_detail:
                    utils.logger.warning(
                        f"[NoteProcessor.batch_get_note_list] Get note detail error: {note_id}"
                    )
                else:
                    await weibo_store.update_weibo_note(note_detail)
            else:
                # 如果未开启微博爬取全文的功能，则直接保存
                await weibo_store.update_weibo_note(note_item)

                # Mark as successfully crawled in checkpoint
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint_id,
                    note_id=note_id,
                    is_success_crawled=True,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                )

        return note_ids

    async def batch_get_specified_notes(
        self, note_id_list: List[str], checkpoint_id: str = ""
    ) -> List[str]:
        """
        Batch get specified notes by ID list
        Args:
            note_id_list: List of note IDs
            checkpoint_id: Checkpoint ID

        Returns:
            List of successfully processed note IDs
        """
        task_list, processed_note_ids = [], []
        for note_id in note_id_list:
            if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=note_id
            ):
                utils.logger.info(
                    f"[NoteProcessor.batch_get_specified_notes] Note {note_id} is already crawled, skip"
                )
                processed_note_ids.append(note_id)
                continue

            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint_id,
                note_id=note_id,
                extra_params_info={},
            )

            task = self.get_note_detail_async_task(
                note_id=note_id,
                checkpoint_id=checkpoint_id,
            )
            task_list.append(task)
            processed_note_ids.append(note_id)

        await asyncio.gather(*task_list)
        return processed_note_ids
