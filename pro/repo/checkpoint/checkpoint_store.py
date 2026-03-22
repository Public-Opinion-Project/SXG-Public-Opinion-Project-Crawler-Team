# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/repo/checkpoint/checkpoint_store.py
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
import os
import sys
from abc import abstractmethod, ABC
import logging
from typing import Any, Dict, Optional
import pathlib
import json
import time
from datetime import datetime

import aiofiles

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(project_root)
sys.path.append(parent_dir)


import config
from model.m_checkpoint import Checkpoint, CheckpointNote
from pkg.cache.abs_cache import AbstractCache
from pkg.cache.cache_factory import CacheFactory

logger = logging.getLogger(__name__)


def generate_checkpoint_id(platform: str, mode: str) -> str:
    """生成基于当前日期时间的检查点ID

    Args:
        platform (str): 平台
        mode (str): 模式

    Returns:
        str: 格式为platform_mode_YYYYMMDDHHMMSS的时间戳字符串，如xhs_search_20250617183823
    """
    return f"{platform}_{mode}_{datetime.now().strftime('%Y%m%d%H%M%S')}"


class BaseCheckpointRepo(ABC):
    @abstractmethod
    async def save_checkpoint(self, checkpoint: Checkpoint) -> Checkpoint:
        """保存检查点

        Args:
            checkpoint (Checkpoint): 检查点

        Returns:
            Checkpoint: 保存后的检查点
        """
        pass

    @abstractmethod
    async def load_checkpoint(
        self,
        platform: Optional[str] = None,
        mode: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """加载检查点

        Args:
            platform (Optional[str]): 平台
            mode (Optional[str]): 模式
            checkpoint_id (str): 检查点ID

        Returns:
            Optional[Checkpoint]: 加载后的检查点
        """
        pass

    @abstractmethod
    async def delete_checkpoint(self, checkpoint_id: str):
        """删除检查点

        Args:
            checkpoint_id (str): 检查点ID
        """
        pass

    @abstractmethod
    async def update_checkpoint(self, checkpoint_id: str, checkpoint: Checkpoint):
        """更新检查点，如果检查点不存在，则保存检查点

        Args:
            checkpoint_id (str): 检查点ID
            checkpoint (Checkpoint): 检查点内容
        """
        pass


class CheckpointJsonFileRepo(BaseCheckpointRepo):

    def __init__(self, cache_dir: str = "data/checkpoints"):
        self.cache_dir = pathlib.Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def save_checkpoint(self, checkpoint: Checkpoint) -> Checkpoint:
        """保存检查点

        Args:
            checkpoint (Checkpoint): 检查点

        Returns:
            Checkpoint: 保存后的检查点
        """
        if checkpoint.id is None:
            checkpoint.id = generate_checkpoint_id(checkpoint.platform, checkpoint.mode)

        checkpoint_file = self.cache_dir / f"{checkpoint.id}.json"
        async with aiofiles.open(checkpoint_file, "w") as f:
            await f.write(json.dumps(checkpoint.model_dump()))

        return checkpoint

    async def load_checkpoint(
        self,
        platform: Optional[str] = None,
        mode: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """加载检查点

        Args:
            platform (Optional[str]): 平台
            mode (Optional[str]): 模式
            checkpoint_id (Optional[str]): 检查点ID
        """
        if not checkpoint_id:
            # 模糊查询，获取最新的检查点
            checkpoint_files = list(self.cache_dir.glob(f"{platform}_{mode}*.json"))
            if not checkpoint_files:
                return None
            checkpoint_file = max(checkpoint_files, key=lambda x: x.stat().st_mtime)
        else:
            checkpoint_file = self.cache_dir / f"{checkpoint_id}.json"
            # 检查文件是否存在
            if not checkpoint_file.exists():
                return None

        async with aiofiles.open(checkpoint_file, "r") as f:
            return Checkpoint.model_validate_json(await f.read())

    async def delete_checkpoint(self, checkpoint_id: str):
        """删除检查点

        Args:
            checkpoint_id (str): 检查点ID
        """
        checkpoint_file = self.cache_dir / f"{checkpoint_id}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()

    async def update_checkpoint(self, checkpoint_id: str, checkpoint: Checkpoint):
        """更新检查点，如果检查点不存在，则保存检查点

        Args:
            checkpoint_id (str): 检查点ID
            checkpoint (Checkpoint): 检查点内容
        """
        # 确保检查点ID一致
        checkpoint.id = checkpoint_id
        await self.save_checkpoint(checkpoint)


class CheckpointRedisRepo(BaseCheckpointRepo):
    """基于Redis的检查点存储库"""

    def __init__(
        self, key_prefix: str = "checkpoint", expire_time: int = 86400 * 7
    ):  # 默认7天过期
        self.key_prefix = key_prefix
        self.expire_time = expire_time  # 检查点过期时间（秒）
        self.redis_cache_client: AbstractCache = CacheFactory.create_cache(
            cache_type=config.CACHE_TYPE_REDIS
        )

    def _get_checkpoint_key(self, checkpoint_id: str) -> str:
        """生成检查点的Redis key"""
        # 解析 checkpoint_id 获取 platform 和 mode
        parts = checkpoint_id.split('_')
        if len(parts) >= 3:
            platform = parts[0]
            mode = parts[1]
            return f"{self.key_prefix}:{platform}:{mode}:{checkpoint_id}"
        return f"{self.key_prefix}:{checkpoint_id}"

    def _get_timestamp_key(self, checkpoint_id: str) -> str:
        """生成时间戳的Redis key，用于记录检查点的创建/更新时间"""
        return f"{self.key_prefix}:timestamp:{checkpoint_id}"

    def get_checkpoint_ttl(self, checkpoint_id: str) -> int:
        """获取检查点的剩余生存时间

        Args:
            checkpoint_id (str): 检查点ID

        Returns:
            int: 剩余生存时间（秒），-1表示永不过期，-2表示键不存在
        """
        checkpoint_key = self._get_checkpoint_key(checkpoint_id)
        return self.redis_cache_client.ttl(checkpoint_key)

    async def save_checkpoint(self, checkpoint: Checkpoint) -> Checkpoint:
        """保存检查点

        Args:
            checkpoint (Checkpoint): 检查点

        Returns:
            Checkpoint: 保存后的检查点
        """
        try:
            if checkpoint.id is None:
                checkpoint.id = generate_checkpoint_id(checkpoint.platform, checkpoint.mode)

            checkpoint_key = self._get_checkpoint_key(checkpoint.id)
            timestamp_key = self._get_timestamp_key(checkpoint.id)

            # 使用AbstractCache接口存储检查点数据
            self.redis_cache_client.set(
                checkpoint_key, checkpoint.model_dump(), self.expire_time
            )

            # 存储时间戳用于后续查询最新检查点
            current_timestamp = int(time.time())
            self.redis_cache_client.set(timestamp_key, current_timestamp, self.expire_time)

            return checkpoint
        except Exception as e:
            logger.error(f"保存检查点失败: {checkpoint.id}, 错误: {e}")
            raise

    async def load_checkpoint(
        self,
        platform: Optional[str] = None,
        mode: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """加载检查点

        Args:
            platform (Optional[str]): 平台
            mode (Optional[str]): 模式
            checkpoint_id (Optional[str]): 检查点ID，如果为None则获取最新的检查点

        Returns:
            Optional[Checkpoint]: 加载后的检查点
        """
        try:
            if not checkpoint_id:
                # 模糊查询，获取最新的检查点
                if not platform or not mode:
                    logger.warning("模糊查询需要提供 platform 和 mode 参数")
                    return None

                pattern = f"{self.key_prefix}:{platform}:{mode}:*"
                keys = self.redis_cache_client.keys(pattern)

                if not keys:
                    return None

                # 获取每个检查点的时间戳，找到最新的
                latest_key = None
                latest_timestamp = 0

                for key in keys:
                    # 从key中提取id
                    checkpoint_id_from_key = key.split(":")[-1]
                    timestamp_key = self._get_timestamp_key(checkpoint_id_from_key)
                    timestamp = self.redis_cache_client.get(timestamp_key)

                    if timestamp:
                        try:
                            timestamp_int = int(timestamp)
                            if timestamp_int > latest_timestamp:
                                latest_timestamp = timestamp_int
                                latest_key = key
                        except (ValueError, TypeError):
                            logger.warning(f"无效的时间戳格式: {timestamp}")
                            continue

                if latest_key is None:
                    return None

                # 获取最新检查点的数据
                checkpoint_data = self.redis_cache_client.get(latest_key)
            else:
                # 精确查询
                checkpoint_key = self._get_checkpoint_key(checkpoint_id)
                checkpoint_data = self.redis_cache_client.get(checkpoint_key)

            if checkpoint_data is None:
                return None

            # 直接验证数据（AbstractCache已经处理了序列化）
            return Checkpoint.model_validate(checkpoint_data)
        except Exception as e:
            logger.error(f"加载检查点失败: platform={platform}, mode={mode}, checkpoint_id={checkpoint_id}, 错误: {e}")
            return None

    async def delete_checkpoint(self, checkpoint_id: str):
        """删除检查点

        Args:
            checkpoint_id (str): 检查点ID
        """
        try:
            checkpoint_key = self._get_checkpoint_key(checkpoint_id)
            timestamp_key = self._get_timestamp_key(checkpoint_id)

            # 删除检查点数据和时间戳
            self.redis_cache_client.delete(checkpoint_key)
            self.redis_cache_client.delete(timestamp_key)
        except Exception as e:
            logger.error(f"删除检查点失败: {checkpoint_id}, 错误: {e}")
            raise

    async def update_checkpoint(self, checkpoint_id: str, checkpoint: Checkpoint):
        """更新检查点，如果检查点不存在，则保存检查点

        Args:
            checkpoint_id (str): 检查点ID
            checkpoint (Checkpoint): 检查点内容
        """
        try:
            # 确保检查点ID一致
            checkpoint.id = checkpoint_id

            # 直接保存/更新检查点（save_checkpoint 已经处理了ID生成和异常）
            await self.save_checkpoint(checkpoint)
        except Exception as e:
            logger.error(f"更新检查点失败: {checkpoint_id}, 错误: {e}")
            raise


class CheckpointRepoManager:
    def __init__(self, checkpoint_repo: BaseCheckpointRepo):
        self.checkpoint_repo = checkpoint_repo
        self.crawler_note_lock = asyncio.Lock()

    async def save_checkpoint(self, checkpoint: Checkpoint) -> Checkpoint:
        """保存检查点

        Args:
            checkpoint (Checkpoint): 检查点
        """
        if checkpoint.id is None:
            checkpoint.id = generate_checkpoint_id(checkpoint.platform, checkpoint.mode)

        await self.checkpoint_repo.save_checkpoint(checkpoint)
        return await self.load_checkpoint(
            checkpoint.platform, checkpoint.mode, checkpoint.id
        )

    async def update_checkpoint(self, checkpoint: Checkpoint) -> Checkpoint:
        """更新检查点

        Args:
            checkpoint (Checkpoint): 检查点
        """
        await self.checkpoint_repo.update_checkpoint(checkpoint.id, checkpoint)
        return await self.load_checkpoint(
            checkpoint.platform, checkpoint.mode, checkpoint.id
        )

    async def add_note_to_checkpoint(
        self,
        checkpoint_id: str,
        note_id: str,
        extra_params_info: Optional[Dict[str, Any]] = None,
        is_success_crawled: bool = False,
    ):
        """添加爬取帖子到检查点

        Args:
            checkpoint_id (Checkpoint): 检查点
            note_id (str): 帖子ID
            extra_params_info (Optional[Dict[str, Any]]): 额外参数信息
            is_success_crawled (bool): 帖子是否成功爬取
        """
        async with self.crawler_note_lock:
            checkpoint = await self.load_checkpoint_by_id(checkpoint_id)
            if checkpoint is None:
                logger.error(f"检查点不存在: {checkpoint_id}")
                raise ValueError(f"检查点不存在: {checkpoint_id}")

            if checkpoint.crawled_note_list is None:
                checkpoint.crawled_note_list = []

            for note in checkpoint.crawled_note_list:
                if note.note_id == note_id:
                    return None

            checkpoint.crawled_note_list.append(
                CheckpointNote(
                    note_id=note_id,
                    extra_params_info=extra_params_info,
                    is_success_crawled=is_success_crawled,
                    is_success_crawled_comments=False,
                    current_note_comment_cursor=None,
                )
            )

            await self.update_checkpoint(checkpoint)
            return None

    async def update_note_to_checkpoint(
        self,
        checkpoint_id: str,
        note_id: str,
        is_success_crawled: bool,
        is_success_crawled_comments: bool,
        current_note_comment_cursor: Optional[str] = None,
        extra_params_info: Optional[Dict[str, Any]] = None,
    ) :
        """更新已爬取的帖子, 需要协程安全

        Args:
            checkpoint_id (str): 检查点ID
            note_id (str): 帖子ID
            is_success_crawled (bool): 是否成功爬取
            is_success_crawled_comments (bool): 是否成功爬取评论
            current_note_comment_cursor (Optional[str]): 当前帖子评论游标
            extra_params_info (Optional[Dict[str, Any]]): 额外参数信息
        """
        async with self.crawler_note_lock:
            checkpoint = await self.load_checkpoint_by_id(checkpoint_id)
            if checkpoint is None:
                logger.error(f"检查点不存在: {checkpoint_id}")
                return False

            for note in checkpoint.crawled_note_list:
                if note.note_id == note_id:
                    note.is_success_crawled = is_success_crawled
                    note.is_success_crawled_comments = is_success_crawled_comments
                    note.current_note_comment_cursor = current_note_comment_cursor
                    if extra_params_info:
                        note.extra_params_info = extra_params_info
                    break

            await self.update_checkpoint(checkpoint)
            return None

    async def load_checkpoint_by_id(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """加载检查点

        Args:
            checkpoint_id (str): 检查点ID
        """
        return await self.load_checkpoint(checkpoint_id=checkpoint_id)

    async def load_checkpoint(
        self,
        platform: Optional[str] = None,
        mode: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """加载检查点, 如果checkpoint_id为空，则加载最新的检查点

        Args:
            platform (Optional[str]): 平台
            mode (Optional[str]): 模式
            checkpoint_id (Optional[str]): 检查点ID
        """
        return await self.checkpoint_repo.load_checkpoint(platform, mode, checkpoint_id)

    async def delete_checkpoint(self, checkpoint_id: str):
        """删除检查点

        Args:
            checkpoint_id (str): 检查点ID
        """
        return await self.checkpoint_repo.delete_checkpoint(checkpoint_id)

    async def check_note_is_crawled_in_checkpoint(
        self, checkpoint_id: str, note_id: str
    ) -> bool:
        """检查点中是否存在该帖子且已爬取

        Args:
            checkpoint_id (str): 检查点ID
            note_id (str): 帖子ID
        """
        checkpoint = await self.load_checkpoint_by_id(checkpoint_id)
        if checkpoint is None:
            return False

        if checkpoint.crawled_note_list is None:
            return False

        for note in checkpoint.crawled_note_list:
            if note.note_id == note_id:
                return note.is_success_crawled

        return False


    async def get_note_info_from_checkpont(self, checkpoint_id: str, note_id: str) -> Optional[CheckpointNote]:
        """
        从检查点获取帖子信息

        Args:
            checkpoint_id:
            note_id:

        Returns:

        """
        checkpoint = await self.load_checkpoint_by_id(checkpoint_id)
        if checkpoint is None:
            return None

        if checkpoint.crawled_note_list is None:
            return None

        for note in checkpoint.crawled_note_list:
            if note.note_id == note_id:
                return note

        return None




    async def check_note_comments_is_crawled_in_checkpoint(
        self, checkpoint_id: str, note_id: str
    ) -> bool:
        """检查点中是否存在该帖子且已爬取评论

        Args:
            checkpoint_id (str): 检查点ID
            note_id (str): 帖子ID
        """
        checkpoint = await self.load_checkpoint_by_id(checkpoint_id)
        if checkpoint is None:
            return False

        if checkpoint.crawled_note_list is None:
            return False

        for note in checkpoint.crawled_note_list:
            if note.note_id == note_id:
                return note.is_success_crawled_comments

        return False

    async def get_note_comment_cursor(
        self, checkpoint_id: str, note_id: str
    ) -> Optional[str]:
        """获取帖子评论游标"""
        checkpoint = await self.load_checkpoint_by_id(checkpoint_id)
        if checkpoint is None:
            return None

        if checkpoint.crawled_note_list is None:
            return None

        for note in checkpoint.crawled_note_list:
            if note.note_id == note_id:
                return note.current_note_comment_cursor

        return None

    async def update_note_comment_cursor(
        self,
        checkpoint_id: str,
        note_id: str,
        comment_cursor: str,
        is_success_crawled_comments: bool = False,
    ) -> bool:
        """更新帖子评论游标

        Args:
            checkpoint_id (str): 检查点ID
            note_id (str): 帖子ID
            comment_cursor (str): 评论游标
            is_success_crawled_comments (bool): 是否成功爬取评论
        """
        async with self.crawler_note_lock:
            checkpoint = await self.load_checkpoint_by_id(checkpoint_id)
            if checkpoint is None:
                logger.error(f"检查点不存在: {checkpoint_id}")
                return False

            for note in checkpoint.crawled_note_list:
                if note.note_id == note_id:
                    note.current_note_comment_cursor = comment_cursor
                    note.is_success_crawled_comments = is_success_crawled_comments
                    break

            await self.update_checkpoint(checkpoint)
            return True
