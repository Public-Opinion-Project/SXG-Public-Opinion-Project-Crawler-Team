# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/bilibili/processors/comment_processor.py
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
from asyncio import Task
from typing import List, TYPE_CHECKING, Dict, Optional, Callable

import config
from config import PER_NOTE_MAX_COMMENTS_COUNT
from model.m_bilibili import VideoIdInfo, BilibiliComment
from pkg.tools import utils
from repo.platform_save_data import bilibili as bilibili_store
from ..exception import DataFetchError
from ..field import CommentOrderType

if TYPE_CHECKING:
    from ..client import BilibiliClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager



class CommentProcessor:
    """Handles comment processing operations including batch processing"""

    def __init__(
        self,
        bili_client: "BilibiliClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_video_comment_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize comment processor

        Args:
            bili_client: Bilibili API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_video_comment_semaphore: Semaphore to limit concurrent comment tasks
        """
        self.bili_client = bili_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_video_comment_semaphore = crawler_video_comment_semaphore

    async def batch_get_video_comments(
        self,
        video_infos: List[VideoIdInfo],
        checkpoint_id: str,
    ):
        """
        Batch get video comments
        Args:
            video_infos: List of VideoIdInfo objects
            checkpoint_id: Checkpoint ID

        Returns:
            None
        """
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(
                f"[CommentProcessor.batch_get_video_comments] Crawling comment mode is not enabled"
            )
            return

        task_list: List[Task] = []
        for video_info in video_infos:
            # 先判断checkpoint中该video的is_success_crawled_comments是否为True，如果为True，则跳过
            if await self.checkpoint_manager.check_note_comments_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=video_info.bvid
            ):
                utils.logger.info(
                    f"[CommentProcessor.batch_get_video_comments] Video {video_info.bvid} is already crawled comments, skip"
                )
                continue

            task = asyncio.create_task(
                self.get_comments_async_task(
                    aid=video_info.aid,
                    bvid=video_info.bvid,
                    checkpoint_id=checkpoint_id,
                ),
                name=video_info.aid,
            )
            task_list.append(task)
        await asyncio.gather(*task_list)

    async def get_comments_async_task(
        self,
        aid: str,
        bvid: str,
        checkpoint_id: str,
    ):
        """
        Get video comments with quantity limitation
        Args:
            aid: video id
            bvid: video id
            checkpoint_id: checkpoint id

        Returns:
            None
        """
        async with self.crawler_video_comment_semaphore:
            utils.logger.info(
                f"[CommentProcessor.get_comments_async_task] Begin get video id comments {bvid}"
            )
            try:
                await self.get_video_all_comments(
                    aid=aid,
                    bvid=bvid,
                    callback=bilibili_store.batch_update_bilibili_video_comments,
                    checkpoint_id=checkpoint_id
                )
            except DataFetchError as ex:
                utils.logger.error(
                    f"[CommentProcessor.get_comments_async_task] get video_id: {aid} comment error: {ex}"
                )
            except Exception as e:
                utils.logger.error(
                    f"[CommentProcessor.get_comments_async_task] may be been blocked, err:{e}"
                )
                raise e

    async def get_video_all_comments(
            self,
            aid: str,
            bvid: str,
            callback: Optional[Callable] = None,
            checkpoint_id: str = "",
    ):
        """
        获取视频所有评论
        Args:
            aid: 视频ID (aid)
            bvid: 视频ID (bvid)
            callback: 回调函数
            checkpoint_id: 检查点ID

        Returns:

        """
        next_page = 0
        lastest_comment_cursor = await self.checkpoint_manager.get_note_comment_cursor(
            checkpoint_id=checkpoint_id, note_id=bvid
        )
        if lastest_comment_cursor:
            utils.logger.info(
                f"[CommentProcessor.get_note_all_comments] Lastest comment cursor: {lastest_comment_cursor}"
            )
            next_page = int(lastest_comment_cursor)

        result = []
        is_end = False
        while not is_end:
            comment_list, response_data = await self.bili_client.get_video_comments(
                aid, CommentOrderType.DEFAULT, next_page
            )
            cursor_info: Dict = response_data.get("cursor", {})
            is_end = cursor_info.get("is_end")
            next_page = cursor_info.get("next")

            # 更新评论游标到checkpoint中
            if next_page:
                await self.checkpoint_manager.update_note_comment_cursor(
                    checkpoint_id=checkpoint_id,
                    note_id=bvid,
                    comment_cursor=str(next_page),
                )

            if callback:
                await callback(aid, comment_list)

            # 爬虫请求间隔时间
            await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
            result.extend(comment_list)

            if (
                    PER_NOTE_MAX_COMMENTS_COUNT
                    and len(result) >= PER_NOTE_MAX_COMMENTS_COUNT
            ):
                utils.logger.info(
                    f"[CommentProcessor.get_note_all_comments] The number of comments exceeds the limit: {PER_NOTE_MAX_COMMENTS_COUNT}"
                )
                break
            sub_comments = await self.get_comments_all_sub_comments(
                aid, comment_list, callback
            )
            result.extend(sub_comments)

        # 更新评论游标，标记为该帖子的评论已爬取
        await self.checkpoint_manager.update_note_comment_cursor(
            checkpoint_id=checkpoint_id,
            note_id=bvid,
            comment_cursor=str(next_page),
            is_success_crawled_comments=True,
        )

        return result

    async def get_comments_all_sub_comments(
            self,
            video_id: str,
            comments: List[BilibiliComment],
            callback: Optional[Callable] = None,
    ) -> List[BilibiliComment]:
        """
        获取指定一级评论下的所有二级评论, 该方法会一直查找一级评论下的所有二级评论信息
        Args:
            video_id: 视频ID
            comments: 评论列表
            callback: 一次评论爬取结束后

        Returns:

        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            return []

        if not comments:
            return []

        result = []
        for comment in comments:
            if int(comment.sub_comment_count or "0") == 0:
                continue
            sub_comment_has_more = True
            rpid = comment.comment_id
            page_num = 1
            page_size = 10
            while sub_comment_has_more:
                sub_comments, response_data = await self.bili_client.get_video_sub_comments(
                    video_id=video_id,
                    root_comment_id=rpid,
                    pn=page_num,
                    ps=page_size,
                    order_mode=CommentOrderType.DEFAULT,
                )
                if callback:
                    await callback(video_id, sub_comments)

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)
                result.extend(sub_comments)
                sub_comment_has_more = (
                        response_data.get("page", {}).get("count", 0) > page_num * page_size
                )
                page_num += 1

        return result
