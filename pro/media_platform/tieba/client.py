# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/tieba/client.py
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

import json
import traceback
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode

import httpx
from httpx import Response
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

import config
from base.base_crawler import AbstractApiClient
from constant.baidu_tieba import TIEBA_URL
from model.m_baidu_tieba import TiebaNote
from pkg.account_pool import AccountWithIpModel
from pkg.account_pool.pool import AccountWithIpPoolManager
from pkg.tools import utils

from .field import SearchNoteType, SearchSortType
from .help import TieBaExtractor


class BaiduTieBaClient(AbstractApiClient):
    def __init__(
            self,
            timeout: int = 10,
            user_agent: str = None,
            account_with_ip_pool: AccountWithIpPoolManager = None,
    ):
        """
        tieba client constructor
        Args:
            timeout:
            user_agent:
            account_with_ip_pool:
        """
        self.timeout = timeout
        self._user_agent = user_agent or utils.get_user_agent()
        self.page_extractor = TieBaExtractor()
        self.account_with_ip_pool = account_with_ip_pool
        self.account_info: Optional[AccountWithIpModel] = None

    @property
    def headers(self):
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Cookie": self._cookies,
            "origin": "https://tieba.baidu.com",
            "referer": "https://tieba.baidu.com",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        }

    @property
    def _proxies(self):
        return (
            self.account_info.ip_info.format_httpx_proxy()
            if self.account_info.ip_info
            else None
        )

    @property
    def _cookies(self):
        # return ""
        return self.account_info.account.cookies

    async def update_account_info(self):
        """
        更新客户端的账号信息, 该方法会一直尝试获取新的账号信息，直到获取到一个有效的账号信息
        Returns:

        """
        have_account = False
        while not have_account:
            utils.logger.info(
                f"[BaiduTieBaClient.update_account_info] try to get a new account"
            )
            self.account_info = (
                await self.account_with_ip_pool.get_account_with_ip_info()
            )
            have_account = await self.pong()
            if not have_account:
                utils.logger.info(
                    f"[BaiduTieBaClient.update_account_info] current account {self.account_info.account.account_name} is invalid, try to get a new one"
                )

    async def mark_account_invalid(self, account_with_ip: AccountWithIpModel):
        """
        标记账号为无效
        Args:
            account_with_ip:

        Returns:

        """
        if self.account_with_ip_pool:
            await self.account_with_ip_pool.mark_account_invalid(
                account_with_ip.account
            )
            await self.account_with_ip_pool.mark_ip_invalid(account_with_ip.ip_info)

    async def check_ip_expired(self):
        """
        检查IP是否过期, 由于IP的过期时间在运行中是不确定的，所以每次请求都需要验证下IP是否过期
        如果过期了，那么需要重新获取一个新的IP，赋值给当前账号信息
        Returns:

        """
        if (
                config.ENABLE_IP_PROXY
                and self.account_info.ip_info
                and self.account_info.ip_info.is_expired
        ):
            utils.logger.info(
                f"[BaiduTieBaClient.request] current ip {self.account_info.ip_info.ip} is expired, "
                f"mark it invalid and try to get a new one"
            )
            await self.account_with_ip_pool.mark_ip_invalid(self.account_info.ip_info)
            self.account_info.ip_info = (
                await self.account_with_ip_pool.proxy_ip_pool.get_proxy()
            )

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(1))
    async def request(self, method, url, **kwargs) -> Union[Response, Dict]:
        """
        封装httpx的公共请求方法，对请求响应做一些处理
        Args:
            method: 请求方法
            url: 请求的URL
            **kwargs: 其他请求参数，例如请求头、请求体等

        Returns:

        """
        await self.check_ip_expired()
        need_return_ori_response = kwargs.get("return_response", False)
        if "return_response" in kwargs:
            del kwargs["return_response"]

        async with httpx.AsyncClient(proxy=self._proxies) as client:
            response = await client.request(
                method, url, timeout=self.timeout, headers=self.headers, **kwargs
            )

        if response.status_code != 200:
            utils.logger.error(
                f"Request failed, method: {method}, url: {url}, status code: {response.status_code}"
            )
            utils.logger.error(f"Request failed, response: {response.text}")
            raise Exception(
                f"Request failed, method: {method}, url: {url}, status code: {response.status_code}"
            )

        if response.text == "" or response.text == "blocked":
            utils.logger.error(f"request params incrr, response.text: {response.text}")
            raise Exception("account blocked")

        if need_return_ori_response:
            return response

        return response.json()

    async def get(self, uri: str, params=None, **kwargs) -> Union[Response, Dict]:
        """
        GET请求，对请求头签名
        Args:
            uri: 请求路由
            params: 请求参数

        Returns:

        """
        final_uri = uri
        if params and isinstance(params, dict):
            final_uri = f"{uri}?" f"{urlencode(params)}"
        try:
            return await self.request(
                method="GET", url=f"{TIEBA_URL}{final_uri}", **kwargs
            )
        except RetryError as e:
            # 获取原始异常
            original_exception = e.last_attempt.exception()
            traceback.print_exception(
                type(original_exception),
                original_exception,
                original_exception.__traceback__,
            )

            utils.logger.error(
                f"[BaiduTieBaClient.get] 请求uri:{uri} 重试均失败了，尝试更换账号与IP再次发起重试"
            )
            try:
                utils.logger.info(
                    f"[BaiduTieBaClient.get] 请求uri:{uri} 尝试更换IP再次发起重试..."
                )
                await self.account_with_ip_pool.mark_ip_invalid(
                    self.account_info.ip_info
                )
                if config.ENABLE_IP_PROXY:
                    self.account_info.ip_info = (
                        await self.account_with_ip_pool.proxy_ip_pool.get_proxy()
                    )
                    return await self.request(
                        method="GET", url=f"{TIEBA_URL}{final_uri}", **kwargs
                    )

            except RetryError as ee:
                # 获取原始异常
                original_exception = ee.last_attempt.exception()
                traceback.print_exception(
                    type(original_exception),
                    original_exception,
                    original_exception.__traceback__,
                )

                utils.logger.error(
                    f"[BaiduTieBaClient.get] 请求uri:{uri}，IP更换后还是失败，尝试更换账号与IP再次发起重试"
                )
                await self.mark_account_invalid(self.account_info)
                await self.update_account_info()
                return await self.request(
                    method="GET", url=f"{TIEBA_URL}{final_uri}", **kwargs
                )

    async def post(self, uri: str, data: dict, **kwargs) -> Dict:
        """
        POST请求，对请求头签名
        Args:
            uri: 请求路由
            data: 请求体参数

        Returns:

        """
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        try:
            return await self.request(
                method="POST", url=f"{TIEBA_URL}{uri}", data=json_str, **kwargs
            )
        except RetryError as e:
            # 获取原始异常
            original_exception = e.last_attempt.exception()
            traceback.print_exception(
                type(original_exception),
                original_exception,
                original_exception.__traceback__,
            )

            utils.logger.error(
                f"[BaiduTieBaClient.post] 请求uri:{uri} 重试均失败了，尝试更换账号与IP再次发起重试"
            )
            try:
                utils.logger.info(
                    f"[BaiduTieBaClient.post] 请求uri:{uri} 尝试更换IP再次发起重试..."
                )
                await self.account_with_ip_pool.mark_ip_invalid(
                    self.account_info.ip_info
                )
                self.account_info.ip_info = (
                    await self.account_with_ip_pool.proxy_ip_pool.get_proxy()
                )
                return await self.request(
                    method="POST", url=f"{TIEBA_URL}{uri}", data=json_str, **kwargs
                )
            except RetryError as ee:
                # 获取原始异常
                original_exception = ee.last_attempt.exception()
                traceback.print_exception(
                    type(original_exception),
                    original_exception,
                    original_exception.__traceback__,
                )

                utils.logger.error(
                    f"[BaiduTieBaClient.post]请求uri:{uri}，IP更换后还是失败，尝试更换账号与IP再次发起重试"
                )
                await self.mark_account_invalid(self.account_info)
                await self.update_account_info()
                return await self.request(
                    method="POST", url=f"{TIEBA_URL}{uri}", data=json_str, **kwargs
                )

    async def pong(self) -> bool:
        """
        用于检查登录态是否失效了
        Returns:

        """
        utils.logger.info("[BaiduTieBaClient.pong] Begin to pong tieba...")
        try:
            uri = "/mo/q/sync"
            async with httpx.AsyncClient(proxy=self._proxies) as client:
                response = await client.get(f"{TIEBA_URL}{uri}", headers=self.headers)

            res: Dict = response.json()
            if res and res.get("no") == 0:
                ping_flag = True
            else:
                utils.logger.warn(
                    f"[BaiduTieBaClient.pong] user not login, will try to login again..."
                )
                ping_flag = False
        except Exception as e:
            utils.logger.error(
                f"[BaiduTieBaClient.pong] Ping xhs failed: {e},current account: {self.account_info.account.account_name} and try to login again..."
            )
            ping_flag = False
        return ping_flag

    async def get_notes_by_keyword(
            self,
            keyword: str,
            page: int = 1,
            page_size: int = 10,
            sort: SearchSortType = SearchSortType.TIME_DESC,
            note_type: SearchNoteType = SearchNoteType.FIXED_THREAD,
    ) -> List[TiebaNote]:
        """
        根据关键词搜索贴吧帖子
        Args:
            keyword: 关键词
            page: 分页第几页
            page_size: 每页大小
            sort: 结果排序方式
            note_type: 帖子类型（主题贴｜主题+回复混合模式）
        Returns:

        """
        uri = "/f/search/res"
        params = {
            "isnew": 1,
            "qw": keyword,
            "rn": page_size,
            "pn": page,
            "sm": sort.value,
            "only_thread": note_type.value,
        }
        response = await self.get(uri, params=params, return_response=True)
        return self.page_extractor.extract_search_note_list(response.text)

    async def get_note_by_id(self, note_id: str) -> TiebaNote:
        """
        根据帖子ID获取帖子详情
        Args:
            note_id:

        Returns:

        """
        uri = f"/p/{note_id}"
        response = await self.get(uri, return_response=True)
        return self.page_extractor.extract_note_detail(response.text)

    async def get_note_comments(self, note_id: str, page: int = 1) -> str:
        """
        获取指定帖子下的所有一级评论
        Args:
            note_id: 帖子ID
            page: 页码

        Returns:

        """
        uri = f"/p/{note_id}"
        params = {"pn": page}
        response = await self.get(uri, params=params, return_response=True)
        return response.text

    async def get_note_sub_comments(self, note_id: str, parment_comment_id: str, tieba_id: str, page: int = 1) -> str:
        """
        获取指定帖子下的所有子评论
        Args:
            note_id: 帖子ID
            parment_comment_id: 父评论ID
            tieba_id: 贴吧ID
            page: 页码

        Returns:

        """
        uri = f"/p/comment"
        params = {
            "tid": note_id,
            "pid": parment_comment_id,
            "fid": tieba_id,
            "pn": page,
        }
        response = await self.get(uri, params=params, return_response=True)
        return response.text

    async def get_notes_by_tieba_name(
            self, tieba_name: str, page_num: int
    ) -> List[TiebaNote]:
        """
        根据贴吧名称获取帖子列表
        Args:
            tieba_name: 贴吧名称
            page_num: 分页数量

        Returns:

        """
        uri = f"/f?kw={tieba_name}&pn={page_num}"
        response = await self.get(uri, return_response=True)
        return self.page_extractor.extract_tieba_note_list(response.text)

    async def get_creator_info_by_url(self, creator_url: str) -> str:
        """
        根据创作者ID获取创作者信息
        Args:
            creator_url: 创作者主页URL

        Returns:

        """
        creator_res = await self.request(
            method="GET", url=creator_url, return_response=True
        )
        return creator_res.text

    async def get_notes_by_creator(self, user_name: str, page_number: int) -> Dict:
        """
        根据创作者获取创作者的所有帖子
        Args:
            user_name:
            page_number:

        Returns:

        """
        uri = f"/home/get/getthread"
        params = {
            "un": user_name,
            "pn": page_number,
            "ie": "utf-8",
            "_": utils.get_current_timestamp(),
        }
        return await self.get(uri, params=params)
