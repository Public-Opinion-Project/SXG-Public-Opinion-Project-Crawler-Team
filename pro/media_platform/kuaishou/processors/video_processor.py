# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/kuaishou/processors/video_processor.py
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
from typing import Dict, List, Optional, TYPE_CHECKING

import config
from model.m_kuaishou import KuaishouVideo
from pkg.tools import utils
from repo.platform_save_data import kuaishou as kuaishou_store
from ..exception import DataFetchError

if TYPE_CHECKING:
    from ..client import KuaiShouApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager


class VideoProcessor:
    """Handles video processing operations including detail extraction and batch processing"""

    def __init__(
        self,
        ks_client: "KuaiShouApiClient",
        checkpoint_manager: "CheckpointRepoManager",
        crawler_video_task_semaphore: asyncio.Semaphore,
    ):
        """
        Initialize video processor

        Args:
            ks_client: Kuaishou API client
            checkpoint_manager: Checkpoint manager for resume functionality
            crawler_video_task_semaphore: Semaphore to limit concurrent video tasks
        """
        self.ks_client = ks_client
        self.checkpoint_manager = checkpoint_manager
        self.crawler_video_task_semaphore = crawler_video_task_semaphore

    async def get_video_detail_async_task(
        self,
        video_id: str,
        checkpoint_id: str = "",
    ) -> Optional[Dict]:
        """
        Get video detail from API

        Args:
            video_id: video id
            checkpoint_id: checkpoint id
        Returns:
            video detail
        """
        video_detail = None
        async with self.crawler_video_task_semaphore:
            try:
                result: Optional[KuaishouVideo] = await self.ks_client.get_video_info(video_id)
                if result:
                    await kuaishou_store.update_kuaishou_video(result)
                    return result

            except DataFetchError as ex:
                utils.logger.error(
                    f"[VideoProcessor.get_video_detail_async_task] Get video detail error: {ex}"
                )
                return None

            except KeyError as ex:
                utils.logger.error(
                    f"[VideoProcessor.get_video_detail_async_task] have not fund video detail video_id:{video_id}, err: {ex}"
                )
                return None

            finally:
                is_success_crawled = video_detail is not None
                await self.checkpoint_manager.update_note_to_checkpoint(
                    checkpoint_id=checkpoint_id,
                    note_id=video_id,
                    is_success_crawled=is_success_crawled,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                )

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

        return video_detail

    async def batch_get_video_list(
        self,
        video_id_list: List[str],
        checkpoint_id: str = "",
    ) -> List[str]:
        """
        Batch get video list with checkpoint support

        Args:
            video_id_list: List of video IDs
            checkpoint_id: checkpoint id for resume functionality

        Returns:
            List of video IDs
        """
        task_list, video_ids = [], []
        for video_id in video_id_list:
            if not video_id:
                continue

            video_ids.append(video_id)
            if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                checkpoint_id=checkpoint_id, note_id=video_id
            ):
                utils.logger.info(
                    f"[VideoProcessor.batch_get_video_list] Video {video_id} is already crawled, skip"
                )
                continue

            await self.checkpoint_manager.add_note_to_checkpoint(
                checkpoint_id=checkpoint_id,
                note_id=video_id,
                extra_params_info={},
            )

            task = self.get_video_detail_async_task(
                video_id=video_id,
                checkpoint_id=checkpoint_id,
            )
            task_list.append(task)

        await asyncio.gather(*task_list)
        return video_ids
