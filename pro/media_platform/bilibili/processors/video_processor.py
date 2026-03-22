# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/bilibili/processors/video_processor.py
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
import sys
from typing import Dict, List, Optional, TYPE_CHECKING
from tenacity import RetryError

from model.m_bilibili import VideoIdInfo, BilibiliVideo
from model.m_checkpoint import CheckpointNote
from pkg.tools import utils
from repo.platform_save_data import bilibili as bilibili_store
from ..exception import DataFetchError

if TYPE_CHECKING:
    from ..client import BilibiliClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class VideoProcessor:
    """Handles video processing operations including detail extraction and batch processing"""

    def __init__(
        self,
        bili_client: "BilibiliClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_video_task_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize video processor

        Args:
            bili_client: Bilibili API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_video_task_semaphore: Semaphore to limit concurrent video tasks
        """
        self.bili_client = bili_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_video_task_semaphore = crawler_video_task_semaphore

    async def get_video_detail_async_task(
        self,
        aid: str,
        bvid: str,
        checkpoint_id: str,
    ) -> Optional[BilibiliVideo]:
        """
        Get video detail from API

        Args:
            aid: video aid
            bvid: video bvid
            checkpoint_id: checkpoint id
        Returns:
            video detail
        """
        video_detail = None
        async with self.crawler_video_task_semaphore:
            try:
                video_detail = await self.bili_client.get_video_info(aid=aid, bvid=bvid)
                if video_detail:
                    await bilibili_store.update_bilibili_video(video_detail)
                    return video_detail

            except DataFetchError as ex:
                utils.logger.error(
                    f"[VideoProcessor.get_video_detail_async_task] Get video detail error: {ex}"
                )
                return None

            except KeyError as ex:
                utils.logger.error(
                    f"[VideoProcessor.get_video_detail_async_task] have not fund video detail video_id:{bvid or aid}, err: {ex}"
                )
                return None

            except RetryError as ex:
                utils.logger.error(
                    f"[VideoProcessor.get_video_detail_async_task] Get video detail error: {ex}"
                )
                return None

            finally:
                extram_params_info: Optional[Dict] = None
                is_success_crawled = video_detail is not None
                if video_detail:
                    video_aid = video_detail.video_id
                    video_vid = video_detail.bvid
                    extram_params_info = {
                        "aid": video_aid,
                        "bvid": video_vid,
                    }
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint_id,
                    note_id=bvid,
                    is_success_crawled=is_success_crawled,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                    extra_params_info=extram_params_info,
                )

    async def batch_get_video_list(
        self, video_list: List[Dict], checkpoint_id: str = ""
    ) -> List[VideoIdInfo]:
        """
        Concurrently obtain the specified video list and save the data
        Args:
            video_list: List of video items
            checkpoint_id: Checkpoint ID

        Returns:
            List of video IDs (aids)
        """
        task_list = []
        video_id_infos: List[VideoIdInfo] = []
        for video_item in video_list:
            aid = str(video_item.get("aid", "") or video_item.get("id", ""))
            bvid = video_item.get("bvid", "")
            if not bvid or not aid:
                utils.logger.warning(
                    "[VideoProcessor.batch_get_videos] bvid or aid is empty, skip"
                )
                continue

            video_id_infos.append(VideoIdInfo(aid=aid, bvid=bvid))
            if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=bvid
            ):
                utils.logger.info(
                    f"[VideoProcessor.batch_get_videos] Video {bvid} is already crawled, skip"
                )
                continue

            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint_id,
                note_id=bvid,
                extra_params_info={
                    "aid": aid,
                    "bvid": bvid,
                },
            )
            task = self.get_video_detail_async_task(
                aid=aid,
                bvid=bvid,
                checkpoint_id=checkpoint_id,
            )
            task_list.append(task)

        await asyncio.gather(*task_list)
        return video_id_infos

    async def batch_get_video_list_from_bvids(
        self, bvids_list: List[str], checkpoint_id: str
    ) -> List[VideoIdInfo]:
        """
        Concurrently obtain the specified video list by bvids and save the data
        Args:
            bvids_list: List of video bvids
            checkpoint_id: Checkpoint ID

        Returns:
            List of video IDs (aids)
        """
        task_list = []
        video_id_infos: List[VideoIdInfo] = []
        for bvid in bvids_list:
            if not bvid:
                continue

            if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=bvid
            ):
                utils.logger.info(
                    f"[VideoProcessor.batch_get_video_list_from_bvids] Video {bvid} is already crawled, skip"
                )
                checkpoint_video_info: Optional[CheckpointNote] = (
                    await self.checkpoint_manager.get_note_info_from_checkpont(
                        checkpoint_id=checkpoint_id, note_id=bvid
                    )
                )
                if checkpoint_video_info and checkpoint_video_info.extra_params_info:
                    video_id_infos.append(
                        VideoIdInfo(
                            aid=checkpoint_video_info.extra_params_info.get("aid"),
                            bvid=checkpoint_video_info.extra_params_info.get("bvid"),
                        )
                    )
                continue

            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint_id,
                note_id=bvid,
            )
            task = self.get_video_detail_async_task(
                aid="",
                bvid=bvid,
                checkpoint_id=checkpoint_id,
            )
            task_list.append(task)

        video_details = await asyncio.gather(*task_list)
        for video_detail in video_details:
            if video_detail:
                video_aid = video_detail.video_id
                video_vid = video_detail.bvid
                if video_aid and video_vid:
                    video_id_infos.append(VideoIdInfo(aid=video_aid, bvid=video_vid))
        return video_id_infos
