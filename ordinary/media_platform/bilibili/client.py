# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/bilibili/client.py
# GitHub：https://github.com/NanmiCoder
# 基于 NON-COMMERCIAL LEARNING LICENSE 1.1 许可证授权
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
哔哩哔哩 API 客户端模块

提供与哔哩哔哩 API 交互的所有方法
包括视频搜索、视频详情、评论、UP主信息、粉丝、关注、动态等
"""

import asyncio
import json
import random
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union
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
from .field import CommentOrderType, SearchOrderType
from .help import BilibiliSign


class BilibiliClient(AbstractApiClient, ProxyRefreshMixin):
    """
    哔哩哔哩 API 客户端类

    继承自 AbstractApiClient 和 ProxyRefreshMixin
    提供对哔哩哔哩 API 的所有 HTTP 请求功能
    支持代理 IP 自动刷新
    """

    def __init__(
        self,
        timeout=60,  # 媒体爬取需要更长超时，哔哩哔哩长视频需要更长的超时时间
        proxy=None,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
        proxy_ip_pool: Optional["ProxyIpPool"] = None,
    ):
        """
        初始化哔哩哔哩客户端

        参数:
            timeout: 请求超时时间（秒），默认60秒
            proxy: 代理服务器地址
            headers: HTTP 请求头
            playwright_page: Playwright 页面对象，用于获取 localStorage
            cookie_dict: Cookie 字典
            proxy_ip_pool: 代理 IP 池对象
        """
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = "https://api.bilibili.com"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        # 初始化代理池（来自 ProxyRefreshMixin）
        self.init_proxy_pool(proxy_ip_pool)

    async def request(self, method, url, **kwargs) -> Any:
        """
        发送 HTTP 请求的通用方法

        每次请求前检查代理是否过期

        参数:
            method: HTTP 方法（GET、POST 等）
            url: 请求 URL
            **kwargs: 其他传递给 httpx 的参数

        返回:
            API 响应数据

        异常:
            DataFetchError: 当请求失败或返回错误时抛出
        """
        # 每次请求前检查代理是否过期
        await self._refresh_proxy_expired()

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        try:
            data: Dict = response.json()
        except json.JSONDecodeError:
            utils.logger.error(f"[BilibiliClient.request] Failed to decode JSON from response. status_code: {response.status_code}, response_text: {response.text}")
            raise DataFetchError(f"Failed to decode JSON, content: {response.text}")
        if data.get("code") != 0:
            raise DataFetchError(data.get("message", "unkonw error"))
        else:
            return data.get("data", {})

    async def pre_request_data(self, req_data: Dict) -> Dict:
        """
        发送签名请求参数

        需要从 localStorage 获取 wbi_img_urls 参数，值格式如下：
        https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png-https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png

        参数:
            req_data: 原始请求参数

        返回:
            签名后的请求参数
        """
        if not req_data:
            return {}
        img_key, sub_key = await self.get_wbi_keys()
        return BilibiliSign(img_key, sub_key).sign(req_data)

    async def get_wbi_keys(self) -> Tuple[str, str]:
        """
        获取最新的 img_key 和 sub_key

        返回:
            元组 (img_key, sub_key)
        """
        local_storage = await self.playwright_page.evaluate("() => window.localStorage")
        wbi_img_urls = local_storage.get("wbi_img_urls", "")
        if not wbi_img_urls:
            img_url_from_storage = local_storage.get("wbi_img_url")
            sub_url_from_storage = local_storage.get("wbi_sub_url")
            if img_url_from_storage and sub_url_from_storage:
                wbi_img_urls = f"{img_url_from_storage}-{sub_url_from_storage}"
        if wbi_img_urls and "-" in wbi_img_urls:
            img_url, sub_url = wbi_img_urls.split("-")
        else:
            resp = await self.request(method="GET", url=self._host + "/x/web-interface/nav")
            img_url: str = resp['wbi_img']['img_url']
            sub_url: str = resp['wbi_img']['sub_url']
        img_key = img_url.rsplit('/', 1)[1].split('.')[0]
        sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
        return img_key, sub_key

    async def get(self, uri: str, params=None, enable_params_sign: bool = True) -> Dict:
        """
        发送 GET 请求

        参数:
            uri: API 路径
            params: 查询参数
            enable_params_sign: 是否启用参数签名，默认启用

        返回:
            API 响应数据
        """
        final_uri = uri
        if enable_params_sign:
            params = await self.pre_request_data(params)
        if isinstance(params, dict):
            final_uri = (f"{uri}?"
                         f"{urlencode(params)}")
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=self.headers)

    async def post(self, uri: str, data: dict) -> Dict:
        """
        发送 POST 请求

        参数:
            uri: API 路径
            data: POST 数据

        返回:
            API 响应数据
        """
        data = await self.pre_request_data(data)
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return await self.request(method="POST", url=f"{self._host}{uri}", data=json_str, headers=self.headers)

    async def pong(self) -> bool:
        """
        检查登录状态是否有效

        返回:
            bool: 登录状态有效返回 True，否则返回 False
        """
        utils.logger.info("[BilibiliClient.pong] Begin pong bilibili...")
        ping_flag = False
        try:
            check_login_uri = "/x/web-interface/nav"
            response = await self.get(check_login_uri)
            if response.get("isLogin"):
                utils.logger.info("[BilibiliClient.pong] Use cache login state get web interface successfull!")
                ping_flag = True
        except Exception as e:
            utils.logger.error(f"[BilibiliClient.pong] Pong bilibili failed: {e}, and try to login again...")
            ping_flag = False
        return ping_flag

    async def update_cookies(self, browser_context: BrowserContext):
        """
        更新客户端的 Cookie

        从浏览器上下文获取最新的 Cookie

        参数:
            browser_context: 浏览器上下文
        """
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def search_video_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        order: SearchOrderType = SearchOrderType.DEFAULT,
        pubtime_begin_s: int = 0,
        pubtime_end_s: int = 0,
    ) -> Dict:
        """
        搜索视频

        参数:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
            order: 排序方式
            pubtime_begin_s: 发布时间开始时间戳
            pubtime_end_s: 发布时间结束时间戳

        返回:
            搜索结果数据
        """
        uri = "/x/web-interface/wbi/search/type"
        post_data = {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "order": order.value,
            "pubtime_begin_s": pubtime_begin_s,
            "pubtime_end_s": pubtime_end_s
        }
        return await self.get(uri, post_data)

    async def get_video_info(self, aid: Union[int, None] = None, bvid: Union[str, None] = None) -> Dict:
        """
        获取视频详情

        aid 和 bvid 二选一提供

        参数:
            aid: 视频 av 号
            bvid: 视频 bv 号

        返回:
            视频详情数据

        异常:
            ValueError: 当未提供任何参数时抛出
        """
        if not aid and not bvid:
            raise ValueError("Please provide at least one parameter: aid or bvid")

        uri = "/x/web-interface/view/detail"
        params = dict()
        if aid:
            params.update({"aid": aid})
        else:
            params.update({"bvid": bvid})
        return await self.get(uri, params, enable_params_sign=False)

    async def get_video_play_url(self, aid: int, cid: int) -> Dict:
        """
        获取视频播放地址

        参数:
            aid: 视频 av 号
            cid: 视频 cid

        返回:
            视频播放地址数据

        异常:
            ValueError: 当 aid 或 cid 无效时抛出
        """
        if not aid or not cid or aid <= 0 or cid <= 0:
            raise ValueError("aid and cid must exist")
        uri = "/x/player/wbi/playurl"
        qn_value = getattr(config, "BILI_QN", 80)
        params = {
            "avid": aid,
            "cid": cid,
            "qn": qn_value,
            "fourk": 1,
            "fnval": 1,
            "platform": "pc",
        }

        return await self.get(uri, params, enable_params_sign=True)

    async def get_video_media(self, url: str) -> Union[bytes, None]:
        """
        获取视频媒体文件内容

        参数:
            url: 视频媒体 URL

        返回:
            视频字节数据，获取失败返回 None
        """
        # 跟随 CDN 302 重定向，将任何 2xx 视为成功（某些接口返回 206）
        async with httpx.AsyncClient(proxy=self.proxy, follow_redirects=True) as client:
            try:
                response = await client.request("GET", url, timeout=self.timeout, headers=self.headers)
                response.raise_for_status()
                if 200 <= response.status_code < 300:
                    return response.content
                utils.logger.error(
                    f"[BilibiliClient.get_video_media] Unexpected status {response.status_code} for {url}"
                )
                return None
            except httpx.HTTPError as exc:
                utils.logger.error(f"[BilibiliClient.get_video_media] {exc.__class__.__name__} for {exc.request.url} - {exc}")
                return None

    async def get_video_comments(
        self,
        video_id: str,
        order_mode: CommentOrderType = CommentOrderType.DEFAULT,
        next: int = 0,
    ) -> Dict:
        """
        获取视频评论

        参数:
            video_id: 视频 ID
            order_mode: 排序方式
            next: 评论分页参数

        返回:
            评论数据
        """
        uri = "/x/v2/reply/wbi/main"
        post_data = {"oid": video_id, "mode": order_mode.value, "type": 1, "ps": 20, "next": next}
        return await self.get(uri, post_data)

    async def get_video_all_comments(
        self,
        video_id: str,
        crawl_interval: float = 1.0,
        is_fetch_sub_comments=False,
        callback: Optional[Callable] = None,
        max_count: int = 10,
    ):
        """
        获取视频的所有评论（包括子评论）

        参数:
            video_id: 视频 ID
            crawl_interval: 爬取间隔（秒）
            is_fetch_sub_comments: 是否获取二级评论
            callback: 回调函数
            max_count: 每个视频最多爬取的评论数

        返回:
            评论列表
        """
        result = []
        is_end = False
        next_page = 0
        max_retries = 3
        while not is_end and len(result) < max_count:
            comments_res = None
            for attempt in range(max_retries):
                try:
                    comments_res = await self.get_video_comments(video_id, CommentOrderType.DEFAULT, next_page)
                    break  # Success
                except DataFetchError as e:
                    if attempt < max_retries - 1:
                        delay = 5 * (2**attempt) + random.uniform(0, 1)
                        utils.logger.warning(f"[BilibiliClient.get_video_all_comments] Retrying video_id {video_id} in {delay:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                    else:
                        utils.logger.error(f"[BilibiliClient.get_video_all_comments] Max retries reached for video_id: {video_id}. Skipping comments. Error: {e}")
                        is_end = True
                        break
            if not comments_res:
                break

            cursor_info: Dict = comments_res.get("cursor")
            if not cursor_info:
                utils.logger.warning(f"[BilibiliClient.get_video_all_comments] Could not find 'cursor' in response for video_id: {video_id}. Skipping.")
                break

            comment_list: List[Dict] = comments_res.get("replies", [])

            # 检查 is_end 和 next 是否存在
            if "is_end" not in cursor_info or "next" not in cursor_info:
                utils.logger.warning(f"[BilibiliClient.get_video_all_comments] 'is_end' or 'next' not in cursor for video_id: {video_id}. Assuming end of comments.")
                is_end = True
            else:
                is_end = cursor_info.get("is_end")
                next_page = cursor_info.get("next")

            if not isinstance(is_end, bool):
                utils.logger.warning(f"[BilibiliClient.get_video_all_comments] 'is_end' is not a boolean for video_id: {video_id}. Assuming end of comments.")
                is_end = True
            if is_fetch_sub_comments:
                for comment in comment_list:
                    comment_id = comment['rpid']
                    if (comment.get("rcount", 0) > 0):
                        {await self.get_video_all_level_two_comments(video_id, comment_id, CommentOrderType.DEFAULT, 10, crawl_interval, callback)}
            if len(result) + len(comment_list) > max_count:
                comment_list = comment_list[:max_count - len(result)]
            if callback:
                await callback(video_id, comment_list)
            await asyncio.sleep(crawl_interval)
            if not is_fetch_sub_comments:
                result.extend(comment_list)
                continue
        return result

    async def get_video_all_level_two_comments(
        self,
        video_id: str,
        level_one_comment_id: int,
        order_mode: CommentOrderType,
        ps: int = 10,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> Dict:
        """
        获取视频的所有二级评论

        参数:
            video_id: 视频 ID
            level_one_comment_id: 一级评论 ID
            order_mode: 排序方式
            ps: 每页数量
            crawl_interval: 爬取间隔
            callback: 回调函数

        返回:
            二级评论数据
        """

        pn = 1
        while True:
            result = await self.get_video_level_two_comments(video_id, level_one_comment_id, pn, ps, order_mode)
            comment_list: List[Dict] = result.get("replies", [])
            if callback:
                await callback(video_id, comment_list)
            await asyncio.sleep(crawl_interval)
            if (int(result["page"]["count"]) <= pn * ps):
                break

            pn += 1

    async def get_video_level_two_comments(
        self,
        video_id: str,
        level_one_comment_id: int,
        pn: int,
        ps: int,
        order_mode: CommentOrderType,
    ) -> Dict:
        """
        获取视频的二级评论

        参数:
            video_id: 视频 ID
            level_one_comment_id: 一级评论 ID
            pn: 页码
            ps: 每页数量
            order_mode: 排序方式

        返回:
            二级评论数据
        """
        uri = "/x/v2/reply/reply"
        post_data = {
            "oid": video_id,
            "mode": order_mode.value,
            "type": 1,
            "ps": ps,
            "pn": pn,
            "root": level_one_comment_id,
        }
        result = await self.get(uri, post_data)
        return result

    async def get_creator_videos(self, creator_id: str, pn: int, ps: int = 30, order_mode: SearchOrderType = SearchOrderType.LAST_PUBLISH) -> Dict:
        """
        获取创作者的所有视频

        参数:
            creator_id: 创作者 ID
            pn: 页码
            ps: 每页数量
            order_mode: 排序方式

        返回:
            创作者视频列表数据
        """
        uri = "/x/space/wbi/arc/search"
        post_data = {
            "mid": creator_id,
            "pn": pn,
            "ps": ps,
            "order": order_mode,
        }
        return await self.get(uri, post_data)

    async def get_creator_info(self, creator_id: int) -> Dict:
        """
        获取创作者信息

        参数:
            creator_id: 创作者 ID

        返回:
            创作者信息数据
        """
        uri = "/x/space/wbi/acc/info"
        post_data = {
            "mid": creator_id,
        }
        return await self.get(uri, post_data)

    async def get_creator_fans(
        self,
        creator_id: int,
        pn: int,
        ps: int = 24,
    ) -> Dict:
        """
        获取创作者粉丝列表

        参数:
            creator_id: 创作者 ID
            pn: 页码
            ps: 每页数量

        返回:
            粉丝列表数据
        """
        uri = "/x/relation/fans"
        post_data = {
            'vmid': creator_id,
            "pn": pn,
            "ps": ps,
            "gaia_source": "main_web",
        }
        return await self.get(uri, post_data)

    async def get_creator_followings(
        self,
        creator_id: int,
        pn: int,
        ps: int = 24,
    ) -> Dict:
        """
        获取创作者关注列表

        参数:
            creator_id: 创作者 ID
            pn: 页码
            ps: 每页数量

        返回:
            关注列表数据
        """
        uri = "/x/relation/followings"
        post_data = {
            "vmid": creator_id,
            "pn": pn,
            "ps": ps,
            "gaia_source": "main_web",
        }
        return await self.get(uri, post_data)

    async def get_creator_dynamics(self, creator_id: int, offset: str = ""):
        """
        获取创作者动态

        参数:
            creator_id: 创作者 ID
            offset: 分页参数

        返回:
            动态数据
        """
        uri = "/x/polymer/web-dynamic/v1/feed/space"
        post_data = {
            "offset": offset,
            "host_mid": creator_id,
            "platform": "web",
        }

        return await self.get(uri, post_data)

    async def get_creator_all_fans(
        self,
        creator_info: Dict,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 100,
    ) -> List:
        """
        获取创作者的所有粉丝

        参数:
            creator_info: 创作者信息
            crawl_interval: 爬取间隔
            callback: 回调函数
            max_count: 最大爬取粉丝数

        返回:
            粉丝列表
        """
        creator_id = creator_info["id"]
        result = []
        pn = config.START_CONTACTS_PAGE
        while len(result) < max_count:
            fans_res: Dict = await self.get_creator_fans(creator_id, pn=pn)
            fans_list: List[Dict] = fans_res.get("list", [])

            pn += 1
            if len(result) + len(fans_list) > max_count:
                fans_list = fans_list[:max_count - len(result)]
            if callback:
                await callback(creator_info, fans_list)
            await asyncio.sleep(crawl_interval)
            if not fans_list:
                break
            result.extend(fans_list)
        return result

    async def get_creator_all_followings(
        self,
        creator_info: Dict,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 100,
    ) -> List:
        """
        获取创作者的所有关注

        参数:
            creator_info: 创作者信息
            crawl_interval: 爬取间隔
            callback: 回调函数
            max_count: 最大爬取关注数

        返回:
            关注列表
        """
        creator_id = creator_info["id"]
        result = []
        pn = config.START_CONTACTS_PAGE
        while len(result) < max_count:
            followings_res: Dict = await self.get_creator_followings(creator_id, pn=pn)
            followings_list: List[Dict] = followings_res.get("list", [])

            pn += 1
            if len(result) + len(followings_list) > max_count:
                followings_list = followings_list[:max_count - len(result)]
            if callback:
                await callback(creator_info, followings_list)
            await asyncio.sleep(crawl_interval)
            if not followings_list:
                break
            result.extend(followings_list)
        return result

    async def get_creator_all_dynamics(
        self,
        creator_info: Dict,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 20,
    ) -> List:
        """
        获取创作者的所有动态

        参数:
            creator_info: 创作者信息
            crawl_interval: 爬取间隔
            callback: 回调函数
            max_count: 最大爬取动态数

        返回:
            动态列表
        """
        creator_id = creator_info["id"]
        result = []
        offset = ""
        has_more = True
        while has_more and len(result) < max_count:
            dynamics_res = await self.get_creator_dynamics(creator_id, offset)
            dynamics_list: List[Dict] = dynamics_res["items"]
            has_more = dynamics_res["has_more"]
            offset = dynamics_res["offset"]
            if len(result) + len(dynamics_list) > max_count:
                dynamics_list = dynamics_list[:max_count - len(result)]
            if callback:
                await callback(creator_info, dynamics_list)
            await asyncio.sleep(crawl_interval)
            result.extend(dynamics_list)
        return result
