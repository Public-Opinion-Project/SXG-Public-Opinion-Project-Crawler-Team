# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/xhs/client.py
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
import json
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_not_exception_type

import config
from base.base_crawler import AbstractApiClient
from proxy.proxy_mixin import ProxyRefreshMixin
from tools import utils

if TYPE_CHECKING:
    from proxy.proxy_ip_pool import ProxyIpPool

from .exception import DataFetchError, IPBlockError, NoteNotFoundError
from .field import SearchNoteType, SearchSortType
from .help import get_search_id
from .extractor import XiaoHongShuExtractor
from .playwright_sign import sign_with_playwright


class XiaoHongShuClient(AbstractApiClient, ProxyRefreshMixin):

    def __init__(
        self,
        timeout=60,  # 如果启用媒体爬取，小红书长视频需要更长的超时时间
        proxy=None,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
        proxy_ip_pool: Optional["ProxyIpPool"] = None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = "https://edith.xiaohongshu.com"
        self._domain = "https://www.xiaohongshu.com"
        self.IP_ERROR_STR = "Network connection error, please check network settings or restart"
        self.IP_ERROR_CODE = 300012
        self.NOTE_NOT_FOUND_CODE = -510000
        self.NOTE_ABNORMAL_STR = "Note status abnormal, please check later"
        self.NOTE_ABNORMAL_CODE = -510001
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        self._extractor = XiaoHongShuExtractor()
        # 初始化代理池（来自 ProxyRefreshMixin）
        self.init_proxy_pool(proxy_ip_pool)

    async def _pre_headers(self, url: str, params: Optional[Dict] = None, payload: Optional[Dict] = None) -> Dict:
        """请求头参数签名（使用 playwright 注入方法）

        参数:
            url: 请求 URL
            params: GET 请求参数
            payload: POST 请求参数

        返回:
            Dict: 签名后的请求头参数
        """
        a1_value = self.cookie_dict.get("a1", "")

        # 确定请求数据、方法和 URI
        if params is not None:
            data = params
            method = "GET"
        elif payload is not None:
            data = payload
            method = "POST"
        else:
            raise ValueError("params or payload is required")

        # 使用 playwright 注入方法生成签名
        signs = await sign_with_playwright(
            page=self.playwright_page,
            uri=url,
            data=data,
            a1=a1_value,
            method=method,
        )

        headers = {
            "X-S": signs["x-s"],
            "X-T": signs["x-t"],
            "x-S-Common": signs["x-s-common"],
            "X-B3-Traceid": signs["x-b3-traceid"],
        }
        self.headers.update(headers)
        return self.headers

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), retry=retry_if_not_exception_type(NoteNotFoundError))
    async def request(self, method, url, **kwargs) -> Union[str, Any]:
        """
        httpx 通用请求方法的封装，处理请求响应
        参数:
            method: 请求方法
            url: 请求 URL
            **kwargs: 其他请求参数，如 headers、body 等

        返回:

        """
        # 每次请求前检查代理是否过期
        await self._refresh_proxy_if_expired()

        # return response.text
        return_response = kwargs.pop("return_response", False)
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        if response.status_code == 471 or response.status_code == 461:
            # 有朝一日也许有人会绕过验证码
            verify_type = response.headers["Verifytype"]
            verify_uuid = response.headers["Verifyuuid"]
            msg = f"CAPTCHA appeared, request failed, Verifytype: {verify_type}, Verifyuuid: {verify_uuid}, Response: {response}"
            utils.logger.error(msg)
            raise Exception(msg)

        if return_response:
            return response.text
        data: Dict = response.json()
        if data["success"]:
            return data.get("data", data.get("success", {}))
        elif data["code"] == self.IP_ERROR_CODE:
            raise IPBlockError(self.IP_ERROR_STR)
        elif data["code"] in (self.NOTE_NOT_FOUND_CODE, self.NOTE_ABNORMAL_CODE):
            raise NoteNotFoundError(f"Note not found or abnormal, code: {data['code']}")
        else:
            err_msg = data.get("msg", None) or f"{response.text}"
            raise DataFetchError(err_msg)

    async def get(self, uri: str, params: Optional[Dict] = None) -> Dict:
        """
        GET 请求，签名请求头
        参数:
            uri: 请求路由
            params: 请求参数

        返回:

        """
        headers = await self._pre_headers(uri, params)
        full_url = f"{self._host}{uri}"

        return await self.request(
            method="GET", url=full_url, headers=headers, params=params
        )

    async def post(self, uri: str, data: dict, **kwargs) -> Dict:
        """
        POST 请求，签名请求头
        参数:
            uri: 请求路由
            data: 请求体参数

        返回:

        """
        headers = await self._pre_headers(uri, payload=data)
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request(
            method="POST",
            url=f"{self._host}{uri}",
            data=json_str,
            headers=headers,
            **kwargs,
        )

    async def get_note_media(self, url: str) -> Union[bytes, None]:
        # 请求前检查代理是否过期
        await self._refresh_proxy_if_expired()

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            try:
                response = await client.request("GET", url, timeout=self.timeout)
                response.raise_for_status()
                if not response.reason_phrase == "OK":
                    utils.logger.error(
                        f"[XiaoHongShuClient.get_note_media] request {url} err, res:{response.text}"
                    )
                    return None
                else:
                    return response.content
            except (
                httpx.HTTPError
            ) as exc:  # 调用 httpx.request 方法时出现错误，如连接错误、客户端错误、服务器错误或响应状态码不是 2xx
                utils.logger.error(
                    f"[XiaoHongShuClient.get_aweme_media] {exc.__class__.__name__} for {exc.request.url} - {exc}"
                )  # Keep original exception type name for developer debugging
                return None

    async def query_self(self) -> Optional[Dict]:
        """
        查询当前用户信息以检查登录状态
        返回:
            Dict: 如果已登录则返回用户信息，否则返回 None
        """
        uri = "/api/sns/web/v1/user/selfinfo"
        headers = await self._pre_headers(uri, params={})
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.get(f"{self._host}{uri}", headers=headers)
            if response.status_code == 200:
                return response.json()
        return None

    async def pong(self) -> bool:
        """
        通过查询当前用户信息来检查登录状态是否仍然有效
        返回:
            bool: 如果已登录返回 True，否则返回 False
        """
        utils.logger.info("[XiaoHongShuClient.pong] Begin to check login state...")
        ping_flag = False
        try:
            self_info: Dict = await self.query_self()
            if self_info and self_info.get("data", {}).get("result", {}).get("success"):
                ping_flag = True
        except Exception as e:
            utils.logger.error(
                f"[XiaoHongShuClient.pong] Check login state failed: {e}, and try to login again..."
            )
            ping_flag = False
        utils.logger.info(f"[XiaoHongShuClient.pong] Login state result: {ping_flag}")
        return ping_flag

    async def update_cookies(self, browser_context: BrowserContext):
        """
        API 客户端提供的更新 cookies 方法，通常在登录成功后调用
        参数:
            browser_context: 浏览器上下文对象

        返回:

        """
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def get_note_by_keyword(
        self,
        keyword: str,
        search_id: str = get_search_id(),
        page: int = 1,
        page_size: int = 20,
        sort: SearchSortType = SearchSortType.GENERAL,
        note_type: SearchNoteType = SearchNoteType.ALL,
    ) -> Dict:
        """
        通过关键词搜索笔记
        参数:
            keyword: 关键词参数
            page: 页码
            page_size: 每页数据长度
            sort: 搜索结果排序方式
            note_type: 要搜索的笔记类型

        返回:

        """
        uri = "/api/sns/web/v1/search/notes"
        data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": search_id,
            "sort": sort.value,
            "note_type": note_type.value,
        }
        return await self.post(uri, data)

    async def get_note_by_id(
        self,
        note_id: str,
        xsec_source: str,
        xsec_token: str,
    ) -> Dict:
        """
        获取笔记详情 API
        参数:
            note_id: 笔记 ID
            xsec_source: 来源渠道
            xsec_token: 从关键词搜索结果列表返回的 Token

        返回:

        """
        if xsec_source == "":
            xsec_source = "pc_search"

        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_source": xsec_source,
            "xsec_token": xsec_token,
        }
        uri = "/api/sns/web/v1/feed"
        res = await self.post(uri, data)
        if res and res.get("items"):
            res_dict: Dict = res["items"][0]["note_card"]
            return res_dict
        # 频繁爬取时，部分笔记可能有结果，部分没有
        utils.logger.error(
            f"[XiaoHongShuClient.get_note_by_id] get note id:{note_id} empty and res:{res}"
        )
        return dict()

    async def get_note_comments(
        self,
        note_id: str,
        xsec_token: str,
        cursor: str = "",
    ) -> Dict:
        """
        获取一级评论 API
        参数:
            note_id: 笔记 ID
            xsec_token: 验证 Token
            cursor: 分页游标

        返回:

        """
        uri = "/api/sns/web/v2/comment/page"
        params = {
            "note_id": note_id,
            "cursor": cursor,
            "top_comment_id": "",
            "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
        }
        return await self.get(uri, params)

    async def get_note_sub_comments(
        self,
        note_id: str,
        root_comment_id: str,
        xsec_token: str,
        num: int = 10,
        cursor: str = "",
    ):
        """
        获取指定父评论下的二级评论 API
        参数:
            note_id: 二级评论的帖子 ID
            root_comment_id: 根评论 ID
            xsec_token: 验证 Token
            num: 分页数量
            cursor: 分页游标

        返回:

        """
        uri = "/api/sns/web/v2/comment/sub/page"
        params = {
            "note_id": note_id,
            "root_comment_id": root_comment_id,
            "num": str(num),
            "cursor": cursor,
            "image_formats": "jpg,webp,avif",
            "top_comment_id": "",
            "xsec_token": xsec_token,
        }
        return await self.get(uri, params)

    async def get_note_all_comments(
        self,
        note_id: str,
        xsec_token: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 10,
    ) -> List[Dict]:
        """
        获取指定笔记下的所有一级评论，此方法将持续获取帖子的所有评论信息
        参数:
            note_id: 笔记 ID
            xsec_token: 验证 Token
            crawl_interval: 每个笔记的爬取延迟（秒）
            callback: 爬取一个笔记结束后的回调函数
            max_count: 每个笔记最多爬取的评论数量
        返回:

        """
        result = []
        comments_has_more = True
        comments_cursor = ""
        while comments_has_more and len(result) < max_count:
            comments_res = await self.get_note_comments(
                note_id=note_id, xsec_token=xsec_token, cursor=comments_cursor
            )
            comments_has_more = comments_res.get("has_more", False)
            comments_cursor = comments_res.get("cursor", "")
            if "comments" not in comments_res:
                utils.logger.info(
                    f"[XiaoHongShuClient.get_note_all_comments] No 'comments' key found in response: {comments_res}"
                )
                break
            comments = comments_res["comments"]
            if len(result) + len(comments) > max_count:
                comments = comments[: max_count - len(result)]
            if callback:
                await callback(note_id, comments)
            await asyncio.sleep(crawl_interval)
            result.extend(comments)
            sub_comments = await self.get_comments_all_sub_comments(
                comments=comments,
                xsec_token=xsec_token,
                crawl_interval=crawl_interval,
                callback=callback,
            )
            result.extend(sub_comments)
        return result

    async def get_comments_all_sub_comments(
        self,
        comments: List[Dict],
        xsec_token: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        获取指定一级评论下的所有二级评论，此方法将持续获取一级评论下的所有二级评论信息
        参数:
            comments: 评论列表
            xsec_token: 验证 Token
            crawl_interval: 每个评论的爬取延迟（秒）
            callback: 爬取一个评论结束后的回调函数

        返回:

        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            utils.logger.info(
                f"[XiaoHongShuCrawler.get_comments_all_sub_comments] Crawling sub_comment mode is not enabled"
            )
            return []

        result = []
        for comment in comments:
            try:
                note_id = comment.get("note_id")
                sub_comments = comment.get("sub_comments")
                if sub_comments and callback:
                    await callback(note_id, sub_comments)

                sub_comment_has_more = comment.get("sub_comment_has_more")
                if not sub_comment_has_more:
                    continue

                root_comment_id = comment.get("id")
                sub_comment_cursor = comment.get("sub_comment_cursor")

                while sub_comment_has_more:
                    try:
                        comments_res = await self.get_note_sub_comments(
                            note_id=note_id,
                            root_comment_id=root_comment_id,
                            xsec_token=xsec_token,
                            num=10,
                            cursor=sub_comment_cursor,
                        )

                        if comments_res is None:
                            utils.logger.info(
                                f"[XiaoHongShuClient.get_comments_all_sub_comments] No response found for note_id: {note_id}"
                            )
                            break
                        sub_comment_has_more = comments_res.get("has_more", False)
                        sub_comment_cursor = comments_res.get("cursor", "")
                        if "comments" not in comments_res:
                            utils.logger.info(
                                f"[XiaoHongShuClient.get_comments_all_sub_comments] No 'comments' key found in response: {comments_res}"
                            )
                            break
                        comments = comments_res["comments"]
                        if callback:
                            await callback(note_id, comments)
                        await asyncio.sleep(crawl_interval)
                        result.extend(comments)
                    except DataFetchError as e:
                        utils.logger.warning(
                            f"[XiaoHongShuClient.get_comments_all_sub_comments] 获取 note_id: {note_id} 的子评论失败，root_comment_id: {root_comment_id}，错误: {e}。跳过此评论的子评论。"
                        )
                        break  # 跳出当前评论的子评论获取循环，继续处理下一个评论
                    except Exception as e:
                        utils.logger.error(
                            f"[XiaoHongShuClient.get_comments_all_sub_comments] 获取 note_id: {note_id} 的子评论时出现意外错误，root_comment_id: {root_comment_id}，错误: {e}"
                        )
                        break
            except Exception as e:
                utils.logger.error(
                    f"[XiaoHongShuClient.get_comments_all_sub_comments] 处理评论时出错：{comment.get('id', 'unknown')}，错误: {e}。继续处理下一个评论。"
                )
                continue  # 继续处理下一个评论
        return result

    async def get_creator_info(
        self, user_id: str, xsec_token: str = "", xsec_source: str = ""
    ) -> Dict:
        """
        通过解析用户主页 HTML 获取用户简介信息
        PC 用户主页有 window.__INITIAL_STATE__ 变量，直接解析即可

        参数:
            user_id: 用户 ID
            xsec_token: 验证 Token（可选，URL 中包含则传入）
            xsec_source: 来源渠道（可选，URL 中包含则传入）

        返回:
            Dict: 用户信息
        """
        # 构建 URI，如果有 xsec 参数则添加到 URL 中
        uri = f"/user/profile/{user_id}"
        if xsec_token and xsec_source:
            uri = f"{uri}?xsec_token={xsec_token}&xsec_source={xsec_source}"

        html_content = await self.request(
            "GET", self._domain + uri, return_response=True, headers=self.headers
        )
        return self._extractor.extract_creator_info_from_html(html_content)

    async def get_notes_by_creator(
        self,
        creator: str,
        cursor: str,
        page_size: int = 30,
        xsec_token: str = "",
        xsec_source: str = "pc_feed",
    ) -> Dict:
        """
        获取创作者的笔记
        参数:
            creator: 创作者 ID
            cursor: 上一页的最后一个笔记 ID
            page_size: 每页数据长度
            xsec_token: 验证 Token
            xsec_source: 来源渠道

        返回:

        """
        uri = f"/api/sns/web/v1/user_posted"
        params = {
            "num": page_size,
            "cursor": cursor,
            "user_id": creator,
            "xsec_token": xsec_token,
            "xsec_source": xsec_source,
        }
        return await self.get(uri, params)

    async def get_all_notes_by_creator(
        self,
        user_id: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        xsec_token: str = "",
        xsec_source: str = "pc_feed",
    ) -> List[Dict]:
        """
        获取指定用户发布的所有帖子，此方法将持续获取用户下的所有帖子信息
        参数:
            user_id: 用户 ID
            crawl_interval: 爬取延迟（秒）
            callback: 一次分页爬取结束后的更新回调函数
            xsec_token: 验证 Token
            xsec_source: 来源渠道

        返回:

        """
        result = []
        notes_has_more = True
        notes_cursor = ""
        while notes_has_more and len(result) < config.CRAWLER_MAX_NOTES_COUNT:
            notes_res = await self.get_notes_by_creator(
                user_id, notes_cursor, xsec_token=xsec_token, xsec_source=xsec_source
            )
            if not notes_res:
                utils.logger.error(
                    f"[XiaoHongShuClient.get_notes_by_creator] 当前创作者可能被小红书封禁，无法访问数据。"
                )
                break

            notes_has_more = notes_res.get("has_more", False)
            notes_cursor = notes_res.get("cursor", "")
            if "notes" not in notes_res:
                utils.logger.info(
                    f"[XiaoHongShuClient.get_all_notes_by_creator] No 'notes' key found in response: {notes_res}"
                )
                break

            notes = notes_res["notes"]
            utils.logger.info(
                f"[XiaoHongShuClient.get_all_notes_by_creator] got user_id:{user_id} notes len : {len(notes)}"
            )

            remaining = config.CRAWLER_MAX_NOTES_COUNT - len(result)
            if remaining <= 0:
                break

            notes_to_add = notes[:remaining]
            if callback:
                await callback(notes_to_add)

            result.extend(notes_to_add)
            await asyncio.sleep(crawl_interval)

        utils.logger.info(
            f"[XiaoHongShuClient.get_all_notes_by_creator] Finished getting notes for user {user_id}, total: {len(result)}"
        )
        return result

    async def get_note_short_url(self, note_id: str) -> Dict:
        """
        获取笔记短链接
        参数:
            note_id: 笔记 ID

        返回:

        """
        uri = f"/api/sns/web/short_url"
        data = {"original_url": f"{self._domain}/discovery/item/{note_id}"}
        return await self.post(uri, data=data, return_response=True)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def get_note_by_id_from_html(
        self,
        note_id: str,
        xsec_source: str,
        xsec_token: str,
        enable_cookie: bool = False,
    ) -> Optional[Dict]:
        """
        通过解析笔记详情页 HTML 获取笔记详情，此接口可能会失败，这里重试 3 次
        复制自 https://github.com/ReaJason/xhs/blob/eb1c5a0213f6fbb592f0a2897ee552847c69ea2d/xhs/core.py#L217-L259
        感谢 ReaJason
        参数:
            note_id:
            xsec_source:
            xsec_token:
            enable_cookie:

        返回:

        """
        url = (
            "https://www.xiaohongshu.com/explore/"
            + note_id
            + f"?xsec_token={xsec_token}&xsec_source={xsec_source}"
        )
        copy_headers = self.headers.copy()
        if not enable_cookie:
            del copy_headers["Cookie"]

        html = await self.request(
            method="GET", url=url, return_response=True, headers=copy_headers
        )

        return self._extractor.extract_note_detail_from_html(note_id, html)
