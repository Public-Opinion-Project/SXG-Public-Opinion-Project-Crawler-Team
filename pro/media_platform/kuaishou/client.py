# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/kuaishou/client.py
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
import json
import traceback
from typing import Callable, Dict, List, Optional, Union, Tuple
from urllib.parse import urlencode

import httpx
from httpx import Response
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

import config
from base.base_crawler import AbstractApiClient
from config import PER_NOTE_MAX_COMMENTS_COUNT
from constant.kuaishou import (
    KUAISHOU_API,
    KUAISHOU_REST_API,
    KUAISHOU_COMMENT_LIST_V2,
    KUAISHOU_SUB_COMMENT_LIST_V2,
)
from pkg.account_pool import AccountWithIpModel
from pkg.account_pool.pool import AccountWithIpPoolManager
from pkg.rpc.sign_srv_client import SignServerClient
from pkg.tools import utils

from .exception import DataFetchError
from .extractor import KuaishouExtractor
from .graphql import KuaiShouGraphQL
from model.m_kuaishou import KuaishouVideo, KuaishouVideoComment, KuaishouCreator


class KuaiShouApiClient(AbstractApiClient):
    def __init__(
        self,
        timeout: int = 10,
        user_agent: str = None,
        account_with_ip_pool: AccountWithIpPoolManager = None,
    ):
        """
        kuaishou client constructor
        Args:
            timeout: 请求超时时间配置
            user_agent: 自定义的User-Agent
            account_with_ip_pool: 账号池管理器
        """
        self.timeout = timeout
        self._user_agent = user_agent or utils.get_user_agent()
        self._sign_client = SignServerClient()
        self._graphql = KuaiShouGraphQL()
        self._extractor = KuaishouExtractor()
        self.account_with_ip_pool = account_with_ip_pool
        self.account_info: Optional[AccountWithIpModel] = None

    @property
    def headers(self):
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Cookie": self._cookies,
            "origin": "https://www.kuaishou.com",
            "referer": "https://www.kuaishou.com/",
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
                f"[KuaiShouApiClient.update_account_info] try to get a new account"
            )
            account_info = await self.account_with_ip_pool.get_account_with_ip_info()
            self.account_info = account_info
            have_account = await self.pong()
            if not have_account:
                utils.logger.info(
                    f"[KuaiShouApiClient.update_account_info] current account {account_info.account.account_name} is invalid, try to get a new one"
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
                f"[KuaiShouApiClient.request] current ip {self.account_info.ip_info.ip} is expired, "
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
        async with httpx.AsyncClient(proxy=self._proxies) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        data: Dict = response.json()
        if data.get("errors"):
            raise DataFetchError(data.get("errors", "unkonw error"))
        else:
            return data.get("data", {})

    async def get(self, uri: str, params=None, **kwargs) -> Dict:
        """
        get请求
        Args:
            uri: 请求路由
            params: 请求参数
            **kwargs: 其他请求参数

        Returns:

        """
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?" f"{urlencode(params)}"
        try:
            return await self.request(
                method="GET", url=f"{KUAISHOU_API}{final_uri}", **kwargs
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
                f"[KuaiShouApiClient.get] 请求uri:{uri} 重试均失败了，尝试更换账号与IP再次发起重试"
            )
            try:
                utils.logger.info(
                    f"[KuaiShouApiClient.get] 请求uri:{uri} 尝试更换IP再次发起重试..."
                )
                await self.account_with_ip_pool.mark_ip_invalid(
                    self.account_info.ip_info
                )
                self.account_info.ip_info = (
                    await self.account_with_ip_pool.proxy_ip_pool.get_proxy()
                )
                return await self.request(
                    method="GET", url=f"{KUAISHOU_API}{final_uri}", **kwargs
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
                    f"[KuaiShouApiClient.get] 请求uri:{uri}，IP更换后还是失败，尝试更换账号与IP再次发起重试"
                )
                await self.mark_account_invalid(self.account_info)
                await self.update_account_info()
                return await self.request(
                    method="GET", url=f"{KUAISHOU_API}{final_uri}", **kwargs
                )

    async def post(self, uri: str, data: dict, **kwargs) -> Dict:
        """
        post请求
        Args:
            uri: 请求路由
            data: 请求体参数
            **kwargs: 其他请求参数

        Returns:

        """
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        try:
            return await self.request(
                method="POST",
                url=f"{KUAISHOU_API}{uri}",
                data=json_str,
                headers=self.headers,
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
                f"[KuaiShouApiClient.post] 请求uri:{uri} 重试均失败了，尝试更换账号与IP再次发起重试"
            )
            try:
                utils.logger.info(
                    f"[KuaiShouApiClient.post] 请求uri:{uri} 尝试更换IP再次发起重试..."
                )
                await self.account_with_ip_pool.mark_ip_invalid(
                    self.account_info.ip_info
                )
                if config.ENABLE_IP_PROXY:
                    self.account_info.ip_info = (
                        await self.account_with_ip_pool.proxy_ip_pool.get_proxy()
                    )
                    return await self.request(
                        method="POST",
                        url=f"{KUAISHOU_API}{uri}",
                        data=json_str,
                        **kwargs,
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
                    f"[KuaiShouApiClient.post]请求uri:{uri}，IP更换后还是失败，尝试更换账号与IP再次发起重试"
                )
                await self.mark_account_invalid(self.account_info)
                await self.update_account_info()
                return await self.request(
                    method="POST", url=f"{KUAISHOU_API}{uri}", data=json_str, **kwargs
                )

    async def pong(self) -> bool:
        """
        快手登录态检测
        Returns:

        """
        utils.logger.info("[KuaiShouApiClient.pong] Begin pong kuaishou...")
        ping_flag = False
        try:
            post_data = {
                "operationName": "visionProfileUserList",
                "variables": {
                    "ftype": 1,
                },
                "query": self._graphql.get("vision_profile_user_list"),
            }
            async with httpx.AsyncClient(proxy=self._proxies) as client:
                response = await client.post(
                    f"{KUAISHOU_API}", json=post_data, headers=self.headers
                )
            res = response.json()
            vision_profile_user_list = res.get("data", {}).get("visionProfileUserList")
            if vision_profile_user_list and vision_profile_user_list.get("result") == 1:
                ping_flag = True
        except Exception as e:
            utils.logger.error(
                f"[KuaiShouApiClient.pong] Pong kuaishou failed: {e}, and try to login again..."
            )
            ping_flag = False
        return ping_flag

    async def search_info_by_keyword(
        self, keyword: str, pcursor: str, search_session_id: str = ""
    ) -> Tuple[List[KuaishouVideo], Dict]:
        """
        关键词搜索接口
        Args:
            keyword: 关键词
            pcursor: 分页游标
            search_session_id: 搜索会话ID

        Returns:
            Tuple[List[KuaishouVideo], Dict]: 视频列表和原始响应

        """
        post_data = {
            "operationName": "visionSearchPhoto",
            "variables": {
                "keyword": keyword,
                "pcursor": pcursor,
                "page": "search",
                "searchSessionId": search_session_id,
            },
            "query": self._graphql.get("search_query"),
        }
        res = await self.post("", post_data)

        # 提取视频列表
        videos = []
        vision_search_photo = res.get("visionSearchPhoto", {})
        feeds = vision_search_photo.get("feeds", [])

        for feed in feeds:
            video = self._extractor.extract_video_from_dict(feed)
            if video:
                videos.append(video)

        return videos, res

    async def get_video_info(self, photo_id: str) -> Optional[KuaishouVideo]:
        """
        获取视频详情
        Args:
            photo_id: 视频id

        Returns:
            KuaishouVideo: 视频模型对象
        """
        post_data = {
            "operationName": "visionVideoDetail",
            "variables": {"photoId": photo_id, "page": "search"},
            "query": self._graphql.get("video_detail"),
        }
        res = await self.post("", post_data)
        video_detail = res.get("visionVideoDetail", {})
        if video_detail:
            return self._extractor.extract_video_from_dict(video_detail)
        return None

    async def get_video_comments(self, photo_id: str, pcursor: str = "") -> Tuple[List[KuaishouVideoComment], Dict]:
        """
        获取视频一级评论
        Args:
            photo_id: 视频id
            pcursor: 分页游标

        Returns:
            Tuple[List[KuaishouVideoComment], Dict]: 评论模型列表和响应元数据
        """
        post_data = {
            "operationName": "commentListQuery",
            "variables": {"photoId": photo_id, "pcursor": pcursor},
            "query": self._graphql.get("comment_list"),
        }
        res = await self.post("", post_data)

        # Handle None response
        if not res:
            return [], {}

        # Extract comments as models
        vision_comment_list = res.get("visionCommentList", {})
        comments_data = vision_comment_list.get("rootComments", [])
        comments = self._extractor.extract_comments_from_list(photo_id, comments_data)

        # Return both models and metadata
        return comments, res

    async def get_video_sub_comments(
        self, photo_id: str, root_comment_id: str, pcursor: str = ""
    ) -> Tuple[List[KuaishouVideoComment], Dict]:
        """
        获取视频二级评论
        Args:
            photo_id: 视频ID
            root_comment_id: 一级评论ID
            pcursor:

        Returns:
            Tuple[List[KuaishouVideoComment], Dict]: 子评论模型列表和响应元数据
        """
        post_data = {
            "operationName": "visionSubCommentList",
            "variables": {
                "photoId": photo_id,
                "pcursor": pcursor,
                "rootCommentId": root_comment_id,
            },
            "query": self._graphql.get("vision_sub_comment_list"),
        }
        res = await self.post("", post_data)

        # Handle None response
        if not res:
            return [], {}

        # Extract sub-comments as models
        vision_sub_comment_list = res.get("visionSubCommentList", {})
        sub_comments_data = vision_sub_comment_list.get("subComments", [])
        sub_comments = self._extractor.extract_comments_from_list(photo_id, sub_comments_data)
        for sub_comment in sub_comments:
            sub_comment.parent_comment_id = root_comment_id

        # Return both models and metadata
        return sub_comments, res

    async def get_creator_profile(self, user_id: str) -> Dict:
        """
        获取创作者主页信息
        Args:
            user_id: 用户ID

        Returns:

        """
        post_data = {
            "operationName": "visionProfile",
            "variables": {"userId": user_id},
            "query": self._graphql.get("vision_profile"),
        }
        return await self.post("", post_data)

    async def get_video_by_creater(self, user_id: str, pcursor: str = "") -> Dict:
        """
        获取用户发布的所有视频
        Args:
            user_id: 用户ID
            pcursor: 分页游标

        Returns:

        """
        post_data = {
            "operationName": "visionProfilePhotoList",
            "variables": {"page": "profile", "pcursor": pcursor, "userId": user_id},
            "query": self._graphql.get("vision_profile_photo_list"),
        }
        return await self.post("", post_data)

    async def get_creator_info(self, user_id: str) -> Optional[KuaishouCreator]:
        """
        获取用户主页信息
        eg: https://www.kuaishou.com/profile/3x4jtnbfter525a
        Args:
            user_id:

        Returns:
            KuaishouCreator: 创作者模型对象
        """
        vision_res = await self.get_creator_profile(user_id)
        vision_profile = vision_res.get("visionProfile", {})
        user_profile = vision_profile.get("userProfile")
        if user_profile:
            return self._extractor.extract_creator_from_dict(user_id, user_profile)
        return None


    async def get_homefeed_videos(self, pcursor: str = "") -> Dict:
        """
        获取快手首页视频

        Args:
            pcursor: 分页游标

        Returns:

        """
        post_data = {
            "operationName": "brilliantTypeDataQuery",
            "variables": {
                "pcursor": pcursor,
                "hotChannelId": "00",
                "page": "brilliant",
            },
            "query": self._graphql.get("homefeed_videos"),
        }
        return await self.post("", post_data)

    # ==================== V2 REST API 方法 ====================

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(1))
    async def request_v2(self, method: str, url: str, **kwargs) -> Dict:
        """
        V2 REST API请求封装

        Args:
            method: 请求方法
            url: 请求URL
            **kwargs: 其他请求参数

        Returns:
            Dict: API响应数据
        """
        async with httpx.AsyncClient(proxy=self._proxies) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        res_data: Dict = response.json()

        # V2 API使用result字段判断成功与否
        if res_data.get("result") != 1:
            raise DataFetchError(f"V2 API error: {res_data}")

        return res_data

    async def post_v2(self, uri: str, data: dict, **kwargs) -> Dict:
        """
        V2 REST API的POST请求

        Args:
            uri: 请求路由
            data: 请求体参数
            **kwargs: 其他请求参数

        Returns:
            Dict: API响应数据
        """
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        try:
            return await self.request_v2(
                method="POST",
                url=f"{KUAISHOU_REST_API}{uri}",
                content=json_str,
                headers=self.headers,
            )
        except RetryError as e:
            original_exception = e.last_attempt.exception()
            traceback.print_exception(
                type(original_exception),
                original_exception,
                original_exception.__traceback__,
            )
            utils.logger.error(
                f"[KuaiShouApiClient.post_v2] 请求uri:{uri} 重试均失败了，尝试更换账号与IP再次发起重试"
            )
            try:
                utils.logger.info(
                    f"[KuaiShouApiClient.post_v2] 请求uri:{uri} 尝试更换IP再次发起重试..."
                )
                await self.account_with_ip_pool.mark_ip_invalid(
                    self.account_info.ip_info
                )
                if config.ENABLE_IP_PROXY:
                    self.account_info.ip_info = (
                        await self.account_with_ip_pool.proxy_ip_pool.get_proxy()
                    )
                    return await self.request_v2(
                        method="POST",
                        url=f"{KUAISHOU_REST_API}{uri}",
                        content=json_str,
                        headers=self.headers,
                    )
            except RetryError as ee:
                original_exception = ee.last_attempt.exception()
                traceback.print_exception(
                    type(original_exception),
                    original_exception,
                    original_exception.__traceback__,
                )
                utils.logger.error(
                    f"[KuaiShouApiClient.post_v2] 请求uri:{uri}，IP更换后还是失败，尝试更换账号与IP再次发起重试"
                )
                await self.mark_account_invalid(self.account_info)
                await self.update_account_info()
                return await self.request_v2(
                    method="POST",
                    url=f"{KUAISHOU_REST_API}{uri}",
                    content=json_str,
                    headers=self.headers,
                )

    async def get_video_comments_v2(
        self, photo_id: str, pcursor: str = ""
    ) -> Tuple[List[KuaishouVideoComment], Dict]:
        """
        获取视频一级评论 - V2 REST API版本

        Args:
            photo_id: 视频id
            pcursor: 分页游标

        Returns:
            Tuple[List[KuaishouVideoComment], Dict]: 评论模型列表和响应元数据
        """
        post_data = {
            "photoId": photo_id,
            "pcursor": pcursor,
        }

        res = await self.post_v2(KUAISHOU_COMMENT_LIST_V2, post_data)

        # Handle None response
        if not res:
            return [], {}

        # 提取评论数据 - V2使用rootCommentsV2
        comments_data = res.get("rootCommentsV2", [])
        comments = self._extractor.extract_comments_from_list_v2(photo_id, comments_data)

        # 返回评论和原始响应数据
        return comments, res

    async def get_video_sub_comments_v2(
        self, photo_id: str, root_comment_id: str, pcursor: str = ""
    ) -> Tuple[List[KuaishouVideoComment], Dict]:
        """
        获取视频二级评论 - V2 REST API版本

        Args:
            photo_id: 视频ID
            root_comment_id: 一级评论ID (V2 API需要数字类型)
            pcursor: 分页游标

        Returns:
            Tuple[List[KuaishouVideoComment], Dict]: 子评论模型列表和响应元数据
        """
        # V2 API的rootCommentId需要是数字类型
        try:
            root_comment_id_int = int(root_comment_id)
        except ValueError:
            root_comment_id_int = root_comment_id

        post_data = {
            "photoId": photo_id,
            "pcursor": pcursor,
            "rootCommentId": root_comment_id_int,
        }

        res = await self.post_v2(KUAISHOU_SUB_COMMENT_LIST_V2, post_data)

        # Handle None response
        if not res:
            return [], {}

        # 提取子评论数据 - V2使用subCommentsV2
        sub_comments_data = res.get("subCommentsV2", [])
        sub_comments = self._extractor.extract_comments_from_list_v2(photo_id, sub_comments_data)

        # 设置父评论ID
        for sub_comment in sub_comments:
            sub_comment.parent_comment_id = str(root_comment_id)

        return sub_comments, res
