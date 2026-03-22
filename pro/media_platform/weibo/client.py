# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/weibo/client.py
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
# @Author  : relakkes@gmail.com
# @Time    : 2023/12/23 15:40
# @Desc    : 微博爬虫 API 请求 client

import asyncio
import copy
import json
import re
from typing import Callable, Dict, List, Optional, Union, cast, Tuple
from urllib.parse import parse_qs, unquote, urlencode

import httpx
from httpx import Response
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

import config
from config import PER_NOTE_MAX_COMMENTS_COUNT
from constant.weibo import WEIBO_API_URL
from model.m_weibo import WeiboNote, WeiboComment, WeiboCreator
from pkg.account_pool import AccountWithIpModel
from pkg.account_pool.pool import AccountWithIpPoolManager
from pkg.proxy import IpInfoModel
from pkg.proxy.proxy_ip_pool import ProxyIpPool
from pkg.tools import utils

from .exception import DataFetchError
from .extractor import WeiboExtractor
from .field import SearchType


class WeiboClient:
    account_info: AccountWithIpModel

    def __init__(
        self,
        timeout: int = 10,
        user_agent: str = None,
        account_with_ip_pool: AccountWithIpPoolManager = None,
    ):
        """
        weibo client constructor
        Args:
            timeout: 请求超时时间
            user_agent: 请求头中的 User-Agent
            account_with_ip_pool: 账号池管理器
        """
        self.timeout = timeout
        self._user_agent = user_agent or utils.get_user_agent()
        self.account_with_ip_pool = account_with_ip_pool
        self._extractor = WeiboExtractor()

    @property
    def headers(self):
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Cookie": self._cookies,
            "origin": "https://m.weibo.cn/",
            "referer": "https://m.weibo.cn/",
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
        return self.account_info.account.cookies

    async def update_account_info(self):
        """
        更新客户端的账号信息, 该方法会一直尝试获取新的账号信息，直到获取到一个有效的账号信息
        Returns:

        """
        have_account = False
        while not have_account:
            utils.logger.info(
                f"[WeiboClient.update_account_info] try to get a new account"
            )
            self.account_info = (
                await self.account_with_ip_pool.get_account_with_ip_info()
            )
            have_account = await self.pong()
            if not have_account:
                utils.logger.info(
                    f"[WeiboClient.update_account_info] current account {self.account_info.account.account_name} is invalid, try to get a new one"
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
            self.account_info.ip_info = await cast(
                ProxyIpPool, self.account_with_ip_pool.proxy_ip_pool
            ).get_proxy()

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
        headers = kwargs.pop("headers", None) or self.headers
        async with httpx.AsyncClient(proxy=self._proxies) as client:
            response = await client.request(
                method, url, timeout=self.timeout, headers=headers, **kwargs
            )

        if need_return_ori_response:
            return response

        data = response.json()
        if data.get("ok") not in [1, 0]:
            # 0和1是正常的返回码，其他的都是异常，0代表无数据，1代表有数据
            utils.logger.error(
                f"[WeiboClient.request] request {method}:{url} err, res:{data}"
            )
            raise DataFetchError(data.get("msg", "unkonw error"))
        else:
            return cast(Dict, data.get("data", {}))

    async def get(self, uri: str, params=None, **kwargs) -> Union[Response, Dict]:
        """
        GET请求，对请求头签名
        Args:
            uri: 请求路由
            params: 请求参数

        Returns:

        """
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?" f"{urlencode(params)}"

        try:
            res = await self.request(
                method="GET", url=f"{WEIBO_API_URL}{final_uri}", **kwargs
            )
            return res
        except RetryError:
            utils.logger.error(
                f"[WeiboClient.get] 请求uri:{uri} 重试均失败了，尝试更换账号与IP再次发起重试"
            )
            if config.ENABLE_IP_PROXY:
                try:
                    utils.logger.info(
                        f"[WeiboClient.get] 请求uri:{uri} 尝试更换IP再次发起重试..."
                    )
                    await self.account_with_ip_pool.mark_ip_invalid(
                        cast(IpInfoModel, self.account_info.ip_info)
                    )
                    proxy_ip_pool: ProxyIpPool = cast(
                        ProxyIpPool, self.account_with_ip_pool.proxy_ip_pool
                    )
                    self.account_info.ip_info = await proxy_ip_pool.get_proxy()
                    return await self.request(
                        method="GET", url=f"{WEIBO_API_URL}{final_uri}", **kwargs
                    )
                except RetryError:
                    pass

            utils.logger.error(
                f"[WeiboClient.get]请求uri:{uri}，IP更换后还是失败，尝试更换账号与IP再次发起重试"
            )
            await self.mark_account_invalid(self.account_info)
            await self.update_account_info()
            return await self.request(
                method="GET", url=f"{WEIBO_API_URL}{final_uri}", **kwargs
            )

    async def post(self, uri: str, data: Dict, **kwargs) -> Union[Response, Dict]:
        """
        POST请求，对请求头签名
        Args:
            uri: 请求路由
            data: 请求体参数

        Returns:

        """
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        try:
            res = await self.request(
                method="POST", url=f"{WEIBO_API_URL}{uri}", data=json_str, **kwargs
            )
            return res
        except RetryError:
            utils.logger.error(
                f"[WeiboClient.post] 请求uri:{uri} 重试均失败了，尝试更换账号与IP再次发起重试"
            )
            if config.ENABLE_IP_PROXY:
                utils.logger.info(
                    f"[WeiboClient.post] 请求uri:{uri} 尝试更换IP再次发起重试..."
                )
                try:
                    await self.account_with_ip_pool.mark_ip_invalid(
                        cast(IpInfoModel, self.account_info.ip_info)
                    )
                    proxy_ip_pool: ProxyIpPool = cast(
                        ProxyIpPool, self.account_with_ip_pool.proxy_ip_pool
                    )
                    self.account_info.ip_info = await proxy_ip_pool.get_proxy()
                    return await self.request(
                        method="POST",
                        url=f"{WEIBO_API_URL}{uri}",
                        data=json_str,
                        **kwargs,
                    )

                except RetryError:
                    pass

            utils.logger.error(
                f"[WeiboClient.post]请求uri:{uri}，IP更换后还是失败，尝试更换账号与IP再次发起重试"
            )
            await self.mark_account_invalid(self.account_info)
            await self.update_account_info()
            return await self.request(
                method="POST", url=f"{WEIBO_API_URL}{uri}", data=json_str, **kwargs
            )

    async def pong(self) -> bool:
        """get a note to check if login state is ok"""
        utils.logger.info(
            f"[WeiboClient.pong] Begin to check account: {self.account_info.account.account_name} login state..."
        )
        ping_flag = False
        try:
            uri = "/api/config"
            async with httpx.AsyncClient(proxy=self._proxies) as client:
                response = await client.request(
                    method="GET",
                    url=f"{WEIBO_API_URL}{uri}",
                    headers=self.headers,
                )
            resp_data: Dict = cast(Dict, response.json())
            print(resp_data)
            if resp_data and resp_data.get("data", {}).get("login"):
                ping_flag = True
            else:
                utils.logger.error(
                    f"[WeiboClient.pong] cookie may be invalid and again login..."
                )
        except Exception as e:
            utils.logger.error(
                f"[WeiboClient.pong] Ping xhs failed: {e},current account: {self.account_info.account.account_name} and try to login again..."
            )
            ping_flag = False
        return ping_flag

    async def get_note_by_keyword(
        self, keyword: str, page: int = 1, search_type: SearchType = SearchType.DEFAULT
    ) -> Tuple[List[WeiboNote], Dict]:
        """
        search note by keyword
        :param keyword: 微博搜搜的关键词
        :param page: 分页参数 -当前页码
        :param search_type: 搜索的类型，见 weibo/filed.py 中的枚举SearchType
        :return: (notes_list, raw_response)
        """
        uri = "/api/container/getIndex"
        containerid = f"100103type={search_type.value}&q={keyword}"
        params = {
            "containerid": containerid,
            "page_type": "searchall",
            "page": page,
        }
        res = cast(Dict, await self.get(uri, params))

        # 提取笔记列表 - 需要处理嵌套的card_group结构
        cards = res.get("cards", [])
        notes = []
        for card in cards:
            if card.get("card_type") == 9:  # 微博类型
                note = self._extractor.extract_note_from_dict(card)
                if note:
                    notes.append(note)
            # 处理嵌套的card_group
            if len(card.get("card_group", [])) > 0:
                card_group = card.get("card_group", [])
                for card_group_item in card_group:
                    if card_group_item.get("card_type") == 9:
                        note = self._extractor.extract_note_from_dict(card_group_item)
                        if note:
                            notes.append(note)

        return notes, res

    async def get_note_comments(
        self, mid_id: str, max_id: int, max_id_type: int = 0
    ) -> Tuple[List[WeiboComment], Dict]:
        """get notes comments
        :param mid_id: 微博ID
        :param max_id: 分页参数ID
        :param max_id_type: 分页参数类型
        :return:
        """
        uri = "/comments/hotflow"
        params = {
            "id": mid_id,
            "mid": mid_id,
            "max_id_type": max_id_type,
        }
        if max_id > 0:
            params.update({"max_id": max_id})

        referer_url = f"https://m.weibo.cn/detail/{mid_id}"
        headers = copy.copy(self.headers)
        headers["Referer"] = referer_url

        res = cast(Dict, await self.get(uri, params, headers=headers))

        # 提取评论列表 - res已经是data的内容了
        comments_data = res.get("data", [])
        comments = self._extractor.extract_comments_from_list(mid_id, comments_data)

        # 返回评论和原始响应（包含分页信息等）
        return comments, res

    async def get_note_info_by_id(self, note_id: str) -> Optional[WeiboNote]:
        """
        根据帖子ID获取详情
        :param note_id:
        :return:
        """
        uri = f"/detail/{note_id}"
        response: Response = cast(Response, await self.get(uri, return_response=True))
        if response.status_code != 200:
            raise DataFetchError(f"get weibo detail err: {response.text}")
        match = re.search(
            r"var \$render_data = (\[.*?\])\[0\]", response.text, re.DOTALL
        )
        if match:
            render_data_json = match.group(1)
            render_data_dict = json.loads(render_data_json)
            note_detail = render_data_dict[0].get("status")
            note_item = {"mblog": note_detail}
            return self._extractor.extract_note_from_dict(note_item)
        else:
            utils.logger.info(
                f"[WeiboClient.get_note_info_by_id] 未找到$render_data的值"
            )
            return None

    async def get_creator_container_info(self, creator_id: str) -> Dict:
        """
        获取用户的容器ID, 容器信息代表着真实请求的API路径
            fid_container_id：用户的微博详情API的容器ID
            lfid_container_id：用户的微博列表API的容器ID
        Args:
            creator_id:

        Returns: {

        """
        # fixed: 107603 + creator_id
        return {
            "fid_container_id": f"107603{creator_id}",
            "lfid_container_id": f"107603{creator_id}",
        }
        response = await self.get(f"/u/{creator_id}", return_response=True)
        m_weibocn_params = response.cookies.get("M_WEIBOCN_PARAMS")
        if not m_weibocn_params:
            raise DataFetchError("get containerid failed")
        m_weibocn_params_dict = parse_qs(unquote(m_weibocn_params))
        return {
            "fid_container_id": m_weibocn_params_dict.get("fid", [""])[0],
            "lfid_container_id": m_weibocn_params_dict.get("lfid", [""])[0],
        }

    async def get_creator_info_by_id(self, creator_id: str) -> Optional[WeiboCreator]:
        """
        根据用户ID获取用户详情
        Args:
            creator_id:

        Returns:

        """
        uri = "/api/container/getIndex"
        container_info = {}
        # container_info = await self.get_creator_container_info(creator_id)
        params = {
            "jumpfrom": "weibocom",
            "type": "uid",
            "value": creator_id,
            "containerid": f"100505{creator_id}",
        }

        user_res = await self.get(uri, params)

        if user_res.get("tabsInfo"):
            tabs: List[Dict] = user_res.get("tabsInfo", {}).get("tabs", [])
            for tab in tabs:
                if tab.get("tabKey") == "weibo":
                    container_info["lfid_container_id"] = tab.get("containerid")
                    break

        user_res.update(container_info)

        # 提取用户信息
        user_info = user_res.get("userInfo", {})
        if user_info:
            return self._extractor.extract_creator_from_dict(user_info)
        return None

    async def get_notes_by_creator(
        self,
        creator: str,
        container_id: str,
        since_id: str = "0",
    ) -> Dict:
        """
        获取博主的笔记
        Args:
            creator: 博主ID
            container_id: 容器ID
            since_id: 上一页最后一条笔记的ID
        Returns:

        """
        uri = "/api/container/getIndex"
        params = {
            "jumpfrom": "weibocom",
            "type": "uid",
            "value": creator,
            "containerid": container_id,
            "since_id": since_id,
        }
        return await self.get(uri, params)
