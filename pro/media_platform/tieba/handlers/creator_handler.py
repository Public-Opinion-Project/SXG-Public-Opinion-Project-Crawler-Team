# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/tieba/handlers/creator_handler.py
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
from typing import List, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from model.m_baidu_tieba import TiebaCreator, TiebaNote
from pkg.tools import utils
from repo.platform_save_data import tieba as tieba_store
from ..help import TieBaExtractor
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import BaiduTieBaClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.note_processor import NoteProcessor
    from ..processors.comment_processor import CommentProcessor


class CreatorHandler(BaseHandler):
    """Handles creator-based crawling operations"""

    def __init__(
            self,
            tieba_client: "BaiduTieBaClient",
            checkpoint_manager: "CheckpointRepoManager",
            note_processor: "NoteProcessor",
            comment_processor: "CommentProcessor"
    ):
        """
        Initialize creator handler

        Args:
            tieba_client: Tieba API client
            checkpoint_manager: Checkpoint manager for resume functionality
            note_processor: Note processing component
            comment_processor: Comment processing component
        """
        super().__init__(tieba_client, checkpoint_manager, note_processor, comment_processor)
        self.extractor = TieBaExtractor()

    async def handle(self) -> None:
        """
        Handle creator-based crawling

        Returns:
            None
        """
        await self.get_creators_and_notes()

    @staticmethod
    def _get_creator_url_list() -> List[str]:
        """
        Get creator URL list

        Returns:
            List[str]: creator URL list
        """
        return config.TIEBA_CREATOR_URL_LIST

    def _find_creator_url_index_in_creator_url_list(self, creator_url: str) -> int:
        """
        Find creator URL index in creator URL list

        Args:
            creator_url: creator URL

        Returns:
            int: creator URL index
        """
        creator_url_list = self._get_creator_url_list()
        for index, creator_url_item in enumerate(creator_url_list):
            if creator_url_item == creator_url:
                return index
        return -1

    async def get_creators_and_notes(self) -> None:
        """
        Get creator's information and their notes and comments
        Returns:
            None
        """
        utils.logger.info(
            "[CreatorHandler.get_creators_and_notes] Begin get tieba creators"
        )
        creator_url_list = self._get_creator_url_list()
        checkpoint = Checkpoint(
            platform=constant.TIEBA_PLATFORM_NAME, mode=constant.CRALER_TYPE_CREATOR
        )

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.TIEBA_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_CREATOR,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[CreatorHandler.get_creators_and_notes] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
                creator_url_index = self._find_creator_url_index_in_creator_url_list(
                    lastest_checkpoint.current_creator_id
                )
                if creator_url_index == -1:
                    utils.logger.error(
                        f"[CreatorHandler.get_creators_and_notes] Creator URL {lastest_checkpoint.current_creator_id} not found in creator URL list"
                    )
                    return
                creator_url_list = creator_url_list[creator_url_index:]

        for creator_url in creator_url_list:
            # 按创作者URL保存检查点
            checkpoint.current_creator_id = creator_url
            await self.checkpoint_manager.save_checkpoint(checkpoint)

            try:
                creator_page_html_content = await self.tieba_client.get_creator_info_by_url(
                    creator_url=creator_url
                )
                creator_info: TiebaCreator = self.extractor.extract_creator_info(
                    creator_page_html_content
                )
                if creator_info:
                    utils.logger.info(
                        f"[CreatorHandler.get_creators_and_notes] creator info: {creator_info}"
                    )
                    await tieba_store.save_creator(user_info=creator_info)

                    # Get all note information of the creator
                    await self.get_all_notes_by_creator(
                        user_name=creator_info.user_name,
                        creator_page_html_content=creator_page_html_content,
                        checkpoint_id=checkpoint.id
                    )

                    # 爬虫请求间隔时间
                    await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

                else:
                    utils.logger.error(
                        f"[CreatorHandler.get_creators_and_notes] get creator info error, creator_url:{creator_url}"
                    )

            except Exception as ex:
                utils.logger.error(
                    f"[CreatorHandler.get_creators_and_notes] Process creator error: {ex}"
                )
                return

            finally:
                lastest_checkpoint = (
                    await self.checkpoint_manager.load_checkpoint_by_id(
                        checkpoint.id
                    )
                )
                if lastest_checkpoint:
                    await self.checkpoint_manager.update_checkpoint(
                        lastest_checkpoint
                    )

    async def get_all_notes_by_creator(
            self,
            user_name: str,
            creator_page_html_content: str = None,
            checkpoint_id: str = "",
    ) -> List[TiebaNote]:
        """
        根据创作者用户名获取创作者所有帖子
        Args:
            user_name: 创作者用户名
            creator_page_html_content: 创作者主页的HTML内容
            checkpoint_id: 检查点ID

        Returns:

        """
        # 百度贴吧比较特殊一些，前10个帖子是直接展示在主页上的，要单独处理，通过API获取不到
        result: List[TiebaNote] = []
        if creator_page_html_content:
            thread_id_list = (
                self.tieba_client.page_extractor.extract_tieba_thread_id_list_from_creator_page(
                    creator_page_html_content
                )
            )
            utils.logger.info(
                f"[CreatorHandler.get_all_notes_by_creator] got user_name:{user_name} thread_id_list len : {len(thread_id_list)}"
            )
            tieba_note_list: List[TiebaNote] = await self.note_processor.batch_get_note_list(
                note_id_list=thread_id_list, checkpoint_id=checkpoint_id
            )
            await self.comment_processor.batch_get_note_comments(tieba_note_list, checkpoint_id=checkpoint_id)

        checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
        if not checkpoint:
            raise Exception(
                f"[CreatorHandler.get_all_notes_by_creator] Get checkpoint error, checkpoint_id: {checkpoint_id}"
            )

        notes_has_more = 1
        page_number = int(checkpoint.current_creator_page or 1)
        page_per_count = 20
        total_get_count = 0
        while notes_has_more == 1 and total_get_count < config.CRAWLER_MAX_NOTES_COUNT:
            notes_res = await self.tieba_client.get_notes_by_creator(user_name, page_number)
            if not notes_res or notes_res.get("no") != 0:
                utils.logger.error(
                    f"[CreatorHandler.get_notes_by_creator] got user_name:{user_name} notes failed, notes_res: {notes_res}"
                )
                break
            notes_data = notes_res.get("data")
            if not notes_data:
                break

            notes_has_more = notes_data.get("has_more")
            notes = notes_data["thread_list"]
            utils.logger.info(
                f"[CreatorHandler.get_all_notes_by_creator] got user_name:{user_name} notes len : {len(notes)}"
            )

            note_id_list = [
                str(note["thread_id"]) for note in notes
            ]
            tieba_note_list: List[TiebaNote] = await self.note_processor.batch_get_note_list(note_id_list, checkpoint_id=checkpoint_id)
            await self.comment_processor.batch_get_note_comments(tieba_note_list, checkpoint_id=checkpoint_id)

            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
            result.extend(notes)
            page_number += 1
            total_get_count += page_per_count

            checkpoint = await self.checkpoint_manager.load_checkpoint_by_id(checkpoint_id)
            checkpoint.current_creator_page = str(page_number)
            await self.checkpoint_manager.update_checkpoint(checkpoint)

        return result
