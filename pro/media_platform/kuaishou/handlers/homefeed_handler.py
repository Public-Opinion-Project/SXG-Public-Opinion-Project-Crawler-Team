# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/kuaishou/handlers/homefeed_handler.py
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
from repo.platform_save_data import kuaishou as kuaishou_store
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..client import KuaiShouApiClient
    from repo.checkpoint.checkpoint_store import CheckpointRepoManager
    from ..processors.video_processor import VideoProcessor
    from ..processors.comment_processor import CommentProcessor


class HomefeedHandler(BaseHandler):
    """Handles homefeed-based crawling operations"""

    def __init__(
            self,
            ks_client: "KuaiShouApiClient",
            checkpoint_manager: "CheckpointRepoManager",
            video_processor: "VideoProcessor",
            comment_processor: "CommentProcessor"
    ):
        """
        Initialize homefeed handler

        Args:
            ks_client: Kuaishou API client
            checkpoint_manager: Checkpoint manager for resume functionality
            video_processor: Video processing component
            comment_processor: Comment processing component
        """
        super().__init__(ks_client, checkpoint_manager, video_processor, comment_processor)

    async def handle(self) -> None:
        """
        Handle homefeed-based crawling

        Returns:
            None
        """
        await self.get_homefeed_videos()

    async def get_homefeed_videos(self) -> None:
        """
        Get homefeed videos and comments with checkpoint support
        Returns:
            None
        """
        utils.logger.info(
            "[HomefeedHandler.get_homefeed_videos] Begin get kuaishou homefeed videos"
        )

        checkpoint = Checkpoint(
            platform=constant.KUAISHOU_PLATFORM_NAME,
            mode=constant.CRALER_TYPE_HOMEFEED,
            current_homefeed_cursor="",
        )

        # 如果开启了断点续爬，则加载检查点
        if config.ENABLE_CHECKPOINT:
            lastest_checkpoint = await self.checkpoint_manager.load_checkpoint(
                platform=constant.KUAISHOU_PLATFORM_NAME,
                mode=constant.CRALER_TYPE_HOMEFEED,
                checkpoint_id=config.SPECIFIED_CHECKPOINT_ID,
            )
            if lastest_checkpoint:
                checkpoint = lastest_checkpoint
                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_videos] Load lastest checkpoint: {lastest_checkpoint.id}"
                )
        await self.checkpoint_manager.save_checkpoint(checkpoint)

        # 从checkpoint恢复游标和计数
        pcursor = checkpoint.current_homefeed_cursor or ""
        saved_video_count = 0

        utils.logger.info(
            f"[HomefeedHandler.get_homefeed_videos] Resume from cursor: {pcursor}, saved_count: {saved_video_count}"
        )

        while saved_video_count <= config.CRAWLER_MAX_NOTES_COUNT:
            try:
                homefeed_videos_res = await self.ks_client.get_homefeed_videos(pcursor)
                if not homefeed_videos_res:
                    utils.logger.info(
                        "[HomefeedHandler.get_homefeed_videos] No more content!"
                    )
                    break

                brilliant_type_data: Dict = homefeed_videos_res.get("brilliantTypeData")
                videos_list: List[Dict] = brilliant_type_data.get("feeds", [])

                if not videos_list:
                    utils.logger.info(
                        "[HomefeedHandler.get_homefeed_videos] No more content!"
                    )
                    break

                video_id_list = []
                for video_detail in videos_list:
                    # 限制爬取数量，避免超过 CRAWLER_MAX_NOTES_COUNT
                    if saved_video_count >= config.CRAWLER_MAX_NOTES_COUNT:
                        utils.logger.info(
                            f"[HomefeedHandler.get_homefeed_videos] Reached max videos count: {config.CRAWLER_MAX_NOTES_COUNT}"
                        )
                        break

                    video_id = video_detail.get("photo", {}).get("id")
                    if not video_id:
                        continue

                    video_id_list.append(video_id)

                    # 检查是否已经爬取过
                    if await self.checkpoint_manager.check_note_is_crawled_in_checkpoint(
                            checkpoint_id=checkpoint.id, note_id=video_id
                    ):
                        utils.logger.info(
                            f"[HomefeedHandler.get_homefeed_videos] video {video_id} is already crawled, skip"
                        )
                        saved_video_count += 1
                        continue

                    await self.checkpoint_manager.add_note_to_checkpoint(
                        checkpoint_id=checkpoint.id,
                        note_id=video_id,
                        extra_params_info={},
                        is_success_crawled=True,
                    )

                    saved_video_count += 1
                    await kuaishou_store.update_kuaishou_video(video_item=video_detail)

                # 批量获取视频评论
                await self.comment_processor.batch_get_video_comments(video_id_list, checkpoint.id)

                pcursor = brilliant_type_data.get("pcursor", "")

                # 爬虫请求间隔时间
                await asyncio.sleep(config.CRAWLER_TIME_SLEEP)

                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_videos] Get homefeed videos, saved_video_count: {saved_video_count}"
                )

            except Exception as ex:
                utils.logger.error(
                    f"[HomefeedHandler.get_homefeed_videos] Get homefeed videos error: {ex}"
                )
                # 发生异常了，则打印当前爬取的游标和计数，用于后续继续爬取
                utils.logger.info(
                    "------------------------------------------记录当前爬取的游标和计数------------------------------------------"
                )
                for i in range(3):
                    utils.logger.error(
                        f"[HomefeedHandler.get_homefeed_videos] Current cursor: {pcursor}, saved_video_count: {saved_video_count}"
                    )
                utils.logger.info(
                    "------------------------------------------记录当前爬取的游标和计数---------------------------------------------------"
                )

                utils.logger.info(
                    f"[HomefeedHandler.get_homefeed_videos] 可以在配置文件中开启断点续爬功能，继续爬取当前位置的信息"
                )
                return

            finally:
                # 更新检查点状态
                lastest_checkpoint = (
                    await self.checkpoint_manager.load_checkpoint_by_id(checkpoint.id)
                )
                lastest_checkpoint.current_homefeed_cursor = pcursor
                await self.checkpoint_manager.update_checkpoint(lastest_checkpoint)

        utils.logger.info(
            "[HomefeedHandler.get_homefeed_videos] Kuaishou homefeed videos crawler finished ..."
        )
