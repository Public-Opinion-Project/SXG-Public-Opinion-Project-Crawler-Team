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
from typing import Dict, List, Optional, TYPE_CHECKING

import config
import constant
from model.m_checkpoint import Checkpoint
from model.m_zhihu import ZhihuContent
from pkg.tools import utils
from repo.platform_save_data import zhihu as zhihu_store
from .base_handler import BaseHandler
from ..help import judge_zhihu_url, ZhihuExtractor

if TYPE_CHECKING:
    from ..client import ZhiHuClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.content_processor import ContentProcessor
    from ..processors.comment_processor import CommentProcessor


class DetailHandler(BaseHandler):
    """Handles detail-based crawling operations for Zhihu"""

    def __init__(
        self,
        zhihu_client: "ZhiHuClient",
        checkpoint_manager: "CheckpointRepoManager",
        content_processor: "ContentProcessor",
        comment_processor: "CommentProcessor",
    ):
        """
        Initialize detail handler

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
        Handle detail-based crawling

        Returns:
            None
        """
        await self.get_specified_notes()

    async def get_specified_notes(self):
        """
        Get the information and comments of the specified posts

        Returns:
            None
        """
        utils.logger.info(
            "[DetailHandler.get_specified_notes] Begin get specified zhihu notes"
        )

        # Initialize checkpoint
        checkpoint = Checkpoint(
            platform=constant.ZHIHU_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_DETAIL,
        )

        # Load checkpoint if enabled
        if config.ENABLE_CHECKPOINT:
            latest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.ZHIHU_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_DETAIL,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if latest_checkpoint:
                checkpoint = latest_checkpoint
                utils.logger.info(
                    f"[DetailHandler.get_specified_notes] Load checkpoint: {latest_checkpoint.id}"
                )

        await self.checkpoint_manager.save_checkpoint(checkpoint)

        all_contents: List[ZhihuContent] = []

        for full_note_url in config.ZHIHU_SPECIFIED_ID_LIST:
            full_note_url = full_note_url.split("?")[0]
            note_type = judge_zhihu_url(full_note_url)

            if note_type == constant.QUESTION_NAME:
                # Handle question URL - get all answers with checkpoint support
                contents = await self._handle_question_answers(
                    full_note_url, checkpoint
                )
                all_contents.extend(contents)
            else:
                # Handle regular content URL (answer, article, zvideo)
                content = await self._handle_single_content(
                    full_note_url, note_type, checkpoint
                )
                if content:
                    all_contents.append(content)

        # Get comments for all contents
        await self.comment_processor.batch_get_content_comments(
            content_list=all_contents,
            checkpoint_id=checkpoint.id,
        )

        utils.logger.info(
            f"[DetailHandler.get_specified_notes] Finished processing {len(all_contents)} contents"
        )

    async def _handle_single_content(
        self,
        full_note_url: str,
        note_type: str,
        checkpoint: Checkpoint,
    ) -> Optional[ZhihuContent]:
        """
        Handle single content URL (answer, article, zvideo)

        Args:
            full_note_url: Full URL of the content
            note_type: Type of content (answer, article, zvideo)
            checkpoint: Checkpoint object

        Returns:
            ZhihuContent or None
        """
        content_id = self._extract_content_id(full_note_url, note_type)
        if not content_id:
            utils.logger.warning(
                f"[DetailHandler._handle_single_content] Cannot extract content_id from {full_note_url}"
            )
            return None

        # Check if content is already crawled
        if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
            checkpoint_id=checkpoint.id, note_id=content_id
        ):
            utils.logger.info(
                f"[DetailHandler._handle_single_content] Content {content_id} already crawled, skip"
            )
            # Load the existing content info for comment processing
            note_info = await self.checkpoint_manager.get_note_info_from_checkpont(
                checkpoint_id=checkpoint.id, note_id=content_id
            )
            if note_info and note_info.extra_params_info:
                content = ZhihuContent()
                content.content_id = content_id
                content.content_type = note_info.extra_params_info.get("content_type", note_type)
                return content
            return None

        utils.logger.info(
            f"[DetailHandler._handle_single_content] Begin get {note_type} info: {full_note_url}"
        )

        content: Optional[ZhihuContent] = None

        try:
            # Add to checkpoint before fetching
            question_id = self._extract_question_id(full_note_url) if note_type == constant.ANSWER_NAME else None
            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint.id,
                note_id=content_id,
                extra_params_info={
                    "content_type": note_type,
                    "question_id": question_id,
                },
            )

            # Fetch content based on type
            if note_type == constant.ANSWER_NAME:
                question_id = self._extract_question_id(full_note_url)
                content = await self.zhihu_client.get_answer_info(question_id, content_id)
            elif note_type == constant.ARTICLE_NAME:
                content = await self.zhihu_client.get_article_info(content_id)
            elif note_type == constant.VIDEO_NAME:
                content = await self.zhihu_client.get_video_info(content_id)

            if content:
                await zhihu_store.update_zhihu_content(content)
                utils.logger.info(
                    f"[DetailHandler._handle_single_content] Saved {note_type} {content_id}"
                )

        except Exception as ex:
            utils.logger.error(
                f"[DetailHandler._handle_single_content] Error processing {full_note_url}: {ex}"
            )

        finally:
            # Update checkpoint status
            is_success = content is not None
            await self.checkpoint_manager.update_note_to_checkpoint(
                checkpoint_id=checkpoint.id,
                note_id=content_id,
                is_success_crawled=is_success,
                is_success_crawled_comments=False,
            )
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

        return content

    async def _handle_question_answers(
        self,
        question_url: str,
        checkpoint: Checkpoint,
    ) -> List[ZhihuContent]:
        """
        Handle question URL - get all answers with checkpoint support

        Args:
            question_url: Question URL
            checkpoint: Checkpoint object

        Returns:
            List of ZhihuContent (answers)
        """
        question_id = question_url.split("/")[-1]
        question_note_id = f"question_{question_id}"

        utils.logger.info(
            f"[DetailHandler._handle_question_answers] Begin get all answers for question {question_id}"
        )

        # Check if question is already fully crawled
        if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
            checkpoint_id=checkpoint.id, note_id=question_note_id
        ):
            utils.logger.info(
                f"[DetailHandler._handle_question_answers] Question {question_id} already crawled"
            )
            return []

        # Get saved pagination params from checkpoint
        question_note = await self.checkpoint_manager.get_note_info_from_checkpont(
            checkpoint_id=checkpoint.id, note_id=question_note_id
        )

        # Default pagination params
        req_params: Dict = {
            "cursor": "",
            "session_id": "",
            "offset": 0,
            "limit": 5,
            "order": "default",
        }

        # Resume from checkpoint if available
        if question_note and question_note.extra_params_info:
            saved_params = question_note.extra_params_info
            req_params["cursor"] = saved_params.get("cursor", "")
            req_params["session_id"] = saved_params.get("session_id", "")
            req_params["offset"] = int(saved_params.get("offset", 0))
            utils.logger.info(
                f"[DetailHandler._handle_question_answers] Resume from cursor: {req_params['cursor']}"
            )
        else:
            # First time - add question to checkpoint
            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint.id,
                note_id=question_note_id,
                extra_params_info=req_params,
            )

        all_answers: List[ZhihuContent] = []
        is_end = False

        while not is_end and len(all_answers) < config.CRAWLER_MAX_NOTES_COUNT:
            try:
                res = await self.zhihu_client.get_answers_by_question_id(
                    question_id, **req_params
                )

                if not res:
                    break

                paging_info = res.get("paging", {})
                is_end = paging_info.get("is_end", True)

                contents = self._extractor.extract_anwser_list_from_questions_feeds(
                    res.get("data", [])
                )

                if contents:
                    # Process each answer
                    for content in contents:
                        await zhihu_store.update_zhihu_content(content)

                        # Add answer to checkpoint
                        await self.checkpoint_manager.add_note_to_checkpoint(
                            checkpoint_id=checkpoint.id,
                            note_id=content.content_id,
                            extra_params_info={
                                "content_type": content.content_type,
                                "question_id": question_id,
                            },
                        )
                        await self.checkpoint_manager.update_note_to_checkpoint(
                            checkpoint_id=checkpoint.id,
                            note_id=content.content_id,
                            is_success_crawled=True,
                            is_success_crawled_comments=False,
                        )

                    all_answers.extend(contents)

                # Extract next page params
                req_params = self._extractor.extract_next_req_params_from_url(
                    paging_info, specific_params=list(req_params.keys())
                )
                if not req_params:
                    break

                # Update checkpoint with current pagination state using API
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint.id,
                    note_id=question_note_id,
                    is_success_crawled=False,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                    extra_params_info={
                        "cursor": req_params.get("cursor", ""),
                        "session_id": req_params.get("session_id", ""),
                        "offset": req_params.get("offset", 0),
                    },
                )

                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

            except Exception as ex:
                utils.logger.error(
                    f"[DetailHandler._handle_question_answers] Error: {ex}"
                )
                break

        # Mark question as fully crawled
        await self.checkpoint_manager.update_note_to_checkpoint(
            checkpoint_id=checkpoint.id,
            note_id=question_note_id,
            is_success_crawled=True,
            is_success_crawled_comments=True,
        )

        utils.logger.info(
            f"[DetailHandler._handle_question_answers] Got {len(all_answers)} answers for question {question_id}"
        )

        return all_answers

    @staticmethod
    def _extract_content_id(url: str, note_type: str) -> str:
        """
        Extract content ID from URL

        Args:
            url: Content URL
            note_type: Content type

        Returns:
            Content ID
        """
        if note_type == constant.ANSWER_NAME:
            # https://www.zhihu.com/question/123/answer/456
            return url.split("/")[-1]
        elif note_type == constant.ARTICLE_NAME:
            # https://www.zhihu.com/p/123
            return url.split("/")[-1]
        elif note_type == constant.VIDEO_NAME:
            # https://www.zhihu.com/zvideo/123
            return url.split("/")[-1]
        return ""

    @staticmethod
    def _extract_question_id(url: str) -> str:
        """
        Extract question ID from answer URL

        Args:
            url: Answer URL (https://www.zhihu.com/question/123/answer/456)

        Returns:
            Question ID
        """
        parts = url.split("/")
        for i, part in enumerate(parts):
            if part == "question" and i + 1 < len(parts):
                return parts[i + 1]
        return ""
