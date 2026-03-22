# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/zhihu/core.py
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


# -*- coding: utf-8 -*-
import asyncio
from typing import Optional

import config
import constant
from base.base_crawler import AbstractCrawler
from pkg.account_pool.pool import AccountWithIpPoolManager
from pkg.proxy.proxy_ip_pool import ProxyIpPool, create_ip_pool
from pkg.tools import utils
from repo.checkpoint import create_checkpoint_manager
from repo.checkpoint.checkpoint_store import CheckpointRepoManager
from var import crawler_type_var

from .client import ZhiHuClient
from .handlers import (
    SearchHandler,
    DetailHandler,
    CreatorHandler,
    HomefeedHandler,
)
from .processors import ContentProcessor, CommentProcessor


class ZhihuCrawler(AbstractCrawler):

    def __init__(self) -> None:
        self.zhihu_client = ZhiHuClient()

        # Initialize checkpoint manager
        self.checkpoint_manager: CheckpointRepoManager = create_checkpoint_manager()

        # Concurrency control semaphores
        self.content_task_semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        self.comment_task_semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)

        # Initialize processors
        self.content_processor = ContentProcessor(
            zhihu_client=self.zhihu_client,
            checkpoint_manager=self.checkpoint_manager,
            content_task_semaphore=self.content_task_semaphore,
        )
        self.comment_processor = CommentProcessor(
            zhihu_client=self.zhihu_client,
            checkpoint_manager=self.checkpoint_manager,
            comment_task_semaphore=self.comment_task_semaphore,
        )

        # Initialize handlers
        self.search_handler = SearchHandler(
            zhihu_client=self.zhihu_client,
            checkpoint_manager=self.checkpoint_manager,
            content_processor=self.content_processor,
            comment_processor=self.comment_processor,
        )
        self.detail_handler = DetailHandler(
            zhihu_client=self.zhihu_client,
            checkpoint_manager=self.checkpoint_manager,
            content_processor=self.content_processor,
            comment_processor=self.comment_processor,
        )
        self.creator_handler = CreatorHandler(
            zhihu_client=self.zhihu_client,
            checkpoint_manager=self.checkpoint_manager,
            content_processor=self.content_processor,
            comment_processor=self.comment_processor,
        )
        self.homefeed_handler = HomefeedHandler(
            zhihu_client=self.zhihu_client,
            checkpoint_manager=self.checkpoint_manager,
            content_processor=self.content_processor,
            comment_processor=self.comment_processor,
        )

    async def async_initialize(self):
        """
        Asynchronous Initialization
        Returns:

        """
        utils.logger.info("[ZhihuCrawler.async_initialize] Begin async initialize")
        utils.logger.info(
            "[ZhihuCrawler.start] Zhihu Crawler start（提醒：zhihu的cookies要用搜索结果页面的cookies，否则搜索接口无法使用） ..."
        )
        # 账号池和IP池的初始化
        proxy_ip_pool: Optional[ProxyIpPool] = None
        if config.ENABLE_IP_PROXY:
            # zhihu对代理验证还行，可以选择长时长的IP，比如30分钟一个IP
            # 快代理：私密代理->按IP付费->专业版->IP有效时长为30分钟, 购买地址：https://www.kuaidaili.com/?ref=ldwkjqipvz6c
            proxy_ip_pool = await create_ip_pool(
                config.IP_PROXY_POOL_COUNT, enable_validate_ip=True
            )

        # 初始化账号池
        account_with_ip_pool = AccountWithIpPoolManager(
            platform_name=constant.ZHIHU_PLATFORM_NAME,
            account_save_type=config.ACCOUNT_POOL_SAVE_TYPE,
            proxy_ip_pool=proxy_ip_pool,
        )
        await account_with_ip_pool.async_initialize()

        self.zhihu_client.account_with_ip_pool = account_with_ip_pool
        await self.zhihu_client.update_account_info()

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
        elif config.CRAWLER_TYPE == constant.CRALER_TYPE_HOMEFEED:
            # Get homefeed notes and comments
            await self.homefeed_handler.handle()
        else:
            utils.logger.error(
                f"[ZhihuCrawler.start] Unsupported crawler type: {config.CRAWLER_TYPE}"
            )

        utils.logger.info("[ZhihuCrawler.start] Zhihu Crawler finished ...")
