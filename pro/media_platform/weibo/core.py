# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/weibo/core.py
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
from typing import Optional

import config
import constant
from base.base_crawler import AbstractCrawler
from pkg.account_pool.pool import AccountWithIpPoolManager
from repo.checkpoint import create_checkpoint_manager
from repo.checkpoint.checkpoint_store import CheckpointRepoManager
from pkg.proxy.proxy_ip_pool import ProxyIpPool, create_ip_pool
from pkg.tools import utils
from var import crawler_type_var

from .client import WeiboClient
from .handlers import SearchHandler, DetailHandler, CreatorHandler
from .processors import NoteProcessor, CommentProcessor


class WeiboCrawler(AbstractCrawler):
    def __init__(self) -> None:
        self.wb_client = WeiboClient()
        self.checkpoint_manager: CheckpointRepoManager = create_checkpoint_manager()

        # 限制并发数
        self.crawler_note_task_semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        self.crawler_note_comment_semaphore = asyncio.Semaphore(
            config.MAX_CONCURRENCY_NUM
        )

        # 初始化帖子处理器，评论处理器
        self.note_processor = NoteProcessor(
            self.wb_client,
            self.checkpoint_manager,
            self.crawler_note_task_semaphore
        )
        self.comment_processor = CommentProcessor(
            self.wb_client,
            self.checkpoint_manager,
            self.crawler_note_comment_semaphore
        )

        # 初始化搜索、详情、创作者处理器
        self.search_handler = SearchHandler(
            self.wb_client,
            self.checkpoint_manager,
            self.note_processor,
            self.comment_processor
        )
        self.detail_handler = DetailHandler(
            self.wb_client,
            self.checkpoint_manager,
            self.note_processor,
            self.comment_processor
        )
        self.creator_handler = CreatorHandler(
            self.wb_client,
            self.checkpoint_manager,
            self.note_processor,
            self.comment_processor
        )

    async def async_initialize(self):
        """
        Asynchronous Initialization
        Returns:

        """
        utils.logger.info(
            "[WeiboCrawler.async_initialize] Begin async initialize"
        )

        # 账号池和IP池的初始化
        proxy_ip_pool: Optional[ProxyIpPool] = None
        if config.ENABLE_IP_PROXY:
            # weibo对代理验证中等，可以选择长时长的IP，比如1-5分钟一个IP
            # 快代理：私密代理->按IP付费->专业版->IP有效时长为1-5分钟, 购买地址：https://www.kuaidaili.com/?ref=ldwkjqipvz6c
            proxy_ip_pool = await create_ip_pool(
                config.IP_PROXY_POOL_COUNT, enable_validate_ip=True
            )

        # 初始化账号池
        account_with_ip_pool = AccountWithIpPoolManager(
            platform_name=constant.WEIBO_PLATFORM_NAME,
            account_save_type=config.ACCOUNT_POOL_SAVE_TYPE,
            proxy_ip_pool=proxy_ip_pool,
        )
        await account_with_ip_pool.async_initialize()

        self.wb_client.account_with_ip_pool = account_with_ip_pool
        await self.wb_client.update_account_info()

        # 设置爬虫类型
        crawler_type_var.set(config.CRAWLER_TYPE)

    async def start(self) -> None:
        """
        Start the crawler
        Returns:

        """
        if config.CRAWLER_TYPE == constant.CRALER_TYPE_SEARCH:
            # Search for notes and retrieve their comment information.
            await self.search_handler.handle()
        elif config.CRAWLER_TYPE == constant.CRALER_TYPE_DETAIL:
            # Get the information and comments of the specified post
            await self.detail_handler.handle()
        elif config.CRAWLER_TYPE == constant.CRALER_TYPE_CREATOR:
            # Get creator's information and their notes and comments
            await self.creator_handler.handle()
        else:
            raise NotImplementedError(
                f"[WeiboCrawler.start] Not support crawler type: {config.CRAWLER_TYPE}"
            )

        utils.logger.info("[WeiboCrawler.start] Weibo Crawler finished ...")
