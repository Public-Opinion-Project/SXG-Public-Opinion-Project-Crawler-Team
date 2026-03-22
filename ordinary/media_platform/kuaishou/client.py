# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/kuaishou/client.py
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


"""
快手 API 客户端模块

提供快手平台的 API 调用实现
包括搜索、视频详情、评论、用户信息等接口
使用 GraphQL 和 REST API V2 进行数据请求
"""

# -*- coding: utf-8 -*-
import asyncio
import json
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page

import config
from base.base_crawler import AbstractApiClient
from proxy.proxy_mixin import ProxyRefreshMixin
from tools import utils

if TYPE_CHECKING:
    from proxy.proxy_ip_pool import ProxyIpPool

from .exception import DataFetchError
from .graphql import KuaiShouGraphQL


class KuaiShouClient(AbstractApiClient, ProxyRefreshMixin):
    """
    快手 API 客户端类
    
    负责与快手 Web API 进行交互
    继承自 AbstractApiClient 和 ProxyRefreshMixin，支持代理 IP 自动刷新
    使用 GraphQL 和 REST API V2 两种方式获取数据
    """
    def __init__(
        self,
        timeout=10,
        proxy=None,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
        proxy_ip_pool: Optional["ProxyIpPool"] = None,
    ):
        """
        初始化快手客户端
        
        参数:
            timeout: 请求超时时间（秒）
            proxy: 代理服务器地址
            headers: HTTP 请求头字典
            playwright_page: Playwright 页面对象
            cookie_dict: Cookie 字典
            proxy_ip_pool: 代理 IP 池对象
        """
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = "https://www.kuaishou.com/graphql"
        self._rest_host = "https://www.kuaishou.com"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        self.graphql = KuaiShouGraphQL()
        # 初始化代理池（来自 ProxyRefreshMixin）
        self.init_proxy_pool(proxy_ip_pool)

    async def request(self, method, url, **kwargs) -> Any:
        """
        发送 HTTP 请求
        
        在每次请求前检查代理是否过期，支持自动刷新代理
        
        参数:
            method: HTTP 请求方法
            url: 请求 URL
            **kwargs: 其他 httpx 请求参数
            
        返回:
            JSON 响应数据
            
        抛出:
            DataFetchError: 数据获取错误
        """
        # 每次请求前检查代理是否过期
        await self._refresh_proxy_if_expired()

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        data: Dict = response.json()
        if data.get("errors"):
            raise DataFetchError(data.get("errors", "unkonw error"))
        else:
            return data.get("data", {})

    async def get(self, uri: str, params=None) -> Dict:
        """
        发送 GET 请求
        
        参数:
            uri: API 接口路径
            params: 查询参数字典
            
        返回:
            JSON 响应数据
        """
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?" f"{urlencode(params)}"
        return await self.request(
            method="GET", url=f"{self._host}{final_uri}", headers=self.headers
        )

    async def post(self, uri: str, data: dict) -> Dict:
        """
        发送 POST 请求（GraphQL）
        
        参数:
            uri: API 接口路径
            data: POST 请求数据
            
        返回:
            JSON 响应数据
        """
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request(
            method="POST", url=f"{self._host}{uri}", data=json_str, headers=self.headers
        )

    async def request_rest_v2(self, uri: str, data: dict) -> Dict:
        """
        发送 REST API V2 请求（用于评论接口）
        
        参数:
            uri: API 端点路径
            data: 请求体
            
        返回:
            响应数据
        """
        await self._refresh_proxy_if_expired()

        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(
                method="POST",
                url=f"{self._rest_host}{uri}",
                data=json_str,
                timeout=self.timeout,
                headers=self.headers,
            )
        result: Dict = response.json()
        if result.get("result") != 1:
            raise DataFetchError(f"REST API V2 error: {result}")
        return result

    async def pong(self) -> bool:
        """
        检查登录状态
        
        通过获取用户列表接口判断是否已登录
        
        返回:
            True 表示已登录，False 表示未登录
        """
        utils.logger.info("[KuaiShouClient.pong] Begin pong kuaishou...")
        ping_flag = False
        try:
            post_data = {
                "operationName": "visionProfileUserList",
                "variables": {
                    "ftype": 1,
                },
                "query": self.graphql.get("vision_profile_user_list"),
            }
            res = await self.post("", post_data)
            if res.get("visionProfileUserList", {}).get("result") == 1:
                ping_flag = True
        except Exception as e:
            utils.logger.error(
                f"[KuaiShouClient.pong] Pong kuaishou failed: {e}, and try to login again..."
            )
            ping_flag = False
        return ping_flag

    async def update_cookies(self, browser_context: BrowserContext):
        """
        更新 Cookie
        
        从浏览器上下文获取最新的 Cookie 并更新到客户端
        """
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def search_info_by_keyword(
        self, keyword: str, pcursor: str, search_session_id: str = ""
    ):
        """
        关键词搜索
        
        调用快手搜索 API 获取搜索结果
        
        参数:
            keyword: 搜索关键词
            pcursor: 分页游标
            search_session_id: 搜索会话 ID
            
        返回:
            搜索结果 JSON 数据
        """
        post_data = {
            "operationName": "visionSearchPhoto",
            "variables": {
                "keyword": keyword,
                "pcursor": pcursor,
                "page": "search",
                "searchSessionId": search_session_id,
            },
            "query": self.graphql.get("search_query"),
        }
        return await self.post("", post_data)

    async def get_video_info(self, photo_id: str) -> Dict:
        """
        获取视频详情
        
        通过视频 ID 获取视频详细信息
        
        参数:
            photo_id: 快手视频 ID
            
        返回:
            视频详情 JSON 数据
        """
        post_data = {
            "operationName": "visionVideoDetail",
            "variables": {"photoId": photo_id, "page": "search"},
            "query": self.graphql.get("video_detail"),
        }
        return await self.post("", post_data)

    async def get_video_comments(self, photo_id: str, pcursor: str = "") -> Dict:
        """
        获取视频一级评论
        
        使用 REST API V2 获取视频评论
        
        参数:
            photo_id: 视频 ID
            pcursor: 分页游标，默认为空
            
        返回:
            包含 rootCommentsV2、pcursorV2、commentCountV2 的字典
        """
        post_data = {
            "photoId": photo_id,
            "pcursor": pcursor,
        }
        return await self.request_rest_v2("/rest/v/photo/comment/list", post_data)

    async def get_video_sub_comments(
        self, photo_id: str, root_comment_id: int, pcursor: str = ""
    ) -> Dict:
        """
        获取视频二级评论（回复评论）
        
        使用 REST API V2 获取指定评论的回复列表
        
        参数:
            photo_id: 视频 ID
            root_comment_id: 父评论 ID（必须是 int 类型）
            pcursor: 分页游标，默认为空
            
        返回:
            包含 subCommentsV2、pcursorV2 的字典
        """
        post_data = {
            "photoId": photo_id,
            "pcursor": pcursor,
            "rootCommentId": root_comment_id,  # V2 API 必须是 int 类型
        }
        return await self.request_rest_v2("/rest/v/photo/comment/sublist", post_data)

    async def get_creator_profile(self, userId: str) -> Dict:
        """
        获取创作者主页信息
        
        参数:
            userId: 用户 ID
            
        返回:
            创作者主页 JSON 数据
        """
        post_data = {
            "operationName": "visionProfile",
            "variables": {"userId": userId},
            "query": self.graphql.get("vision_profile"),
        }
        return await self.post("", post_data)

    async def get_video_by_creater(self, userId: str, pcursor: str = "") -> Dict:
        """
        获取创作者发布的视频列表
        
        参数:
            userId: 用户 ID
            pcursor: 分页游标
            
        返回:
            视频列表 JSON 数据
        """
        post_data = {
            "operationName": "visionProfilePhotoList",
            "variables": {"page": "profile", "pcursor": pcursor, "userId": userId},
            "query": self.graphql.get("vision_profile_photo_list"),
        }
        return await self.post("", post_data)

    async def get_video_all_comments(
        self,
        photo_id: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 10,
    ):
        """
        获取视频所有评论，包括子评论（V2 REST API）
        
        参数:
            photo_id: 视频 ID
            crawl_interval: 请求间隔（秒）
            callback: 处理评论的回调函数
            max_count: 最大获取评论数量
            
        返回:
            所有评论列表
        """

        result = []
        pcursor = ""

        while pcursor != "no_more" and len(result) < max_count:
            comments_res = await self.get_video_comments(photo_id, pcursor)
            # V2 API 在顶层返回数据，不嵌套在 visionCommentList 中
            pcursor = comments_res.get("pcursorV2", "no_more")
            comments = comments_res.get("rootCommentsV2", [])
            if len(result) + len(comments) > max_count:
                comments = comments[: max_count - len(result)]
            if callback:  # 如果有回调函数，执行回调函数
                await callback(photo_id, comments)
            result.extend(comments)
            await asyncio.sleep(crawl_interval)
            sub_comments = await self.get_comments_all_sub_comments(
                comments, photo_id, crawl_interval, callback
            )
            result.extend(sub_comments)
        return result

    async def get_comments_all_sub_comments(
        self,
        comments: List[Dict],
        photo_id,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        获取指定一级评论下的所有二级评论（V2 REST API）
        
        参数:
            comments: 一级评论列表
            photo_id: 视频 ID
            crawl_interval: 爬取间隔（秒）
            callback: 爬取完成后的回调函数
            
        返回:
            二级评论列表
        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            utils.logger.info(
                f"[KuaiShouClient.get_comments_all_sub_comments] 爬取子评论模式未启用"
            )
            return []

        result = []
        for comment in comments:
            # V2 API 使用 hasSubComments（布尔值）代替 subCommentsPcursor（字符串）
            has_sub_comments = comment.get("hasSubComments", False)
            if not has_sub_comments:
                continue

            # V2 API 使用 comment_id（int）代替 commentId（string）
            root_comment_id = comment.get("comment_id")
            if not root_comment_id:
                continue

            sub_comment_pcursor = ""

            while sub_comment_pcursor != "no_more":
                comments_res = await self.get_video_sub_comments(
                    photo_id, root_comment_id, sub_comment_pcursor
                )
                # V2 API 在顶层返回数据
                sub_comment_pcursor = comments_res.get("pcursorV2", "no_more")
                sub_comments = comments_res.get("subCommentsV2", [])

                if callback and sub_comments:
                    await callback(photo_id, sub_comments)
                await asyncio.sleep(crawl_interval)
                result.extend(sub_comments)
        return result

    async def get_creator_info(self, user_id: str) -> Dict:
        """
        获取用户信息
        
        例如：https://www.kuaishou.com/profile/3x4jtnbfter525a
        
        参数:
            user_id: 用户 ID
            
        返回:
            用户信息 JSON 数据
        """

        visionProfile = await self.get_creator_profile(user_id)
        return visionProfile.get("userProfile")

    async def get_all_videos_by_creator(
        self,
        user_id: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        获取指定用户发布的所有视频
        
        此方法会持续查找用户下的所有视频信息
        
        参数:
            user_id: 用户 ID
            crawl_interval: 爬取间隔（秒）
            callback: 爬取完成后的回调函数
            
        返回:
            所有视频列表
        """
        result = []
        pcursor = ""

        while pcursor != "no_more":
            videos_res = await self.get_video_by_creater(user_id, pcursor)
            if not videos_res:
                utils.logger.error(
                    f"[KuaiShouClient.get_all_videos_by_creator] 当前创作者可能已被快手封禁，无法访问数据。"
                )
                break

            vision_profile_photo_list = videos_res.get("visionProfilePhotoList", {})
            pcursor = vision_profile_photo_list.get("pcursor", "")

            videos = vision_profile_photo_list.get("feeds", [])
            utils.logger.info(
                f"[KuaiShouClient.get_all_videos_by_creator] got user_id:{user_id} videos len : {len(videos)}"
            )

            if callback:
                await callback(videos)
            await asyncio.sleep(crawl_interval)
            result.extend(videos)
        return result
