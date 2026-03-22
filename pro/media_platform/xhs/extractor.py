# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/xhs/extractor.py
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
import re
from typing import Dict, List, Optional

import humps
from model.m_xhs import XhsComment, XhsCreator, XhsNote, NoteUrlInfo, CreatorUrlInfo
from pkg.tools.crawler_util import extract_url_params_to_dict
from var import source_keyword_var


class XiaoHongShuExtractor:
    def __init__(self):
        pass

    def extract_note_detail_from_html(
        self, note_id: str, html: str
    ) -> Optional[XhsNote]:
        """从html中提取笔记详情

        Args:
            note_id: 笔记ID
            html: html字符串

        Returns:
            XhsNote: 笔记模型对象
        """
        if "noteDetailMap" not in html:
            # 这种情况要么是出了验证码了，要么是笔记不存在
            return None

        state = re.findall(r"window.__INITIAL_STATE__=({.*})</script>", html)[
            0
        ].replace("undefined", '""')
        if state != "{}":
            note_dict = humps.decamelize(json.loads(state))
            note_data = note_dict["note"]["note_detail_map"][note_id]["note"]
            return self._extract_note_from_dict(note_data)
        return None

    def extract_creator_info_from_html(
        self, user_id: str, html: str
    ) -> Optional[XhsCreator]:
        """从html中提取用户信息

        Args:
            user_id: 用户ID
            html: html字符串

        Returns:
            XhsCreator: 创作者模型对象
        """
        match = re.search(
            r"<script>window.__INITIAL_STATE__=(.+)<\/script>", html, re.M
        )
        if match is None:
            return None
        info = json.loads(match.group(1).replace(":undefined", ":null"), strict=False)
        if info is None:
            return None
        creator_data = info.get("user").get("userPageData")
        return self._extract_creator_from_dict(user_id, creator_data)

    def extract_note_from_dict(self, note_data: Dict) -> Optional[XhsNote]:
        """从API响应字典中提取笔记信息

        Args:
            note_data: API响应的笔记数据

        Returns:
            XhsNote: 笔记模型对象
        """
        if not note_data:
            return None
        return self._extract_note_from_dict(note_data)

    def _extract_note_from_dict(self, note_item: Dict) -> XhsNote:
        """内部方法：从字典提取笔记信息"""
        user_info = note_item.get("user", {})
        interact_info = note_item.get("interact_info", {})
        image_list: List[Dict] = note_item.get("image_list", [])
        tag_list: List[Dict] = note_item.get("tag_list", [])

        # 处理图片URL
        for img in image_list:
            if img.get("url_default"):
                img["url"] = img.get("url_default")

        # 处理视频URL
        video_url = ",".join(self._get_video_url_arr(note_item))

        return XhsNote(
            note_id=note_item.get("note_id", ""),
            type=note_item.get("type", ""),
            title=note_item.get("title") or note_item.get("desc", "")[:255],
            desc=note_item.get("desc", ""),
            video_url=video_url,
            time=str(note_item.get("time", "")),
            last_update_time=str(note_item.get("last_update_time", "")),
            user_id=user_info.get("user_id", ""),
            nickname=user_info.get("nickname", ""),
            avatar=user_info.get("avatar", ""),
            liked_count=str(interact_info.get("liked_count", "")),
            collected_count=str(interact_info.get("collected_count", "")),
            comment_count=str(interact_info.get("comment_count", "")),
            share_count=str(interact_info.get("share_count", "")),
            ip_location=note_item.get("ip_location", ""),
            image_list=",".join([img.get("url", "") for img in image_list]),
            tag_list=",".join(
                [tag.get("name", "") for tag in tag_list if tag.get("type") == "topic"]
            ),
            note_url=f"https://www.xiaohongshu.com/explore/{note_item.get('note_id')}?xsec_token={note_item.get('xsec_token', '')}&xsec_source=pc_search",
            source_keyword=source_keyword_var.get(),
        )

    def _get_video_url_arr(self, note_item: Dict) -> List[str]:
        """获取视频URL数组"""
        if note_item.get("type") != "video":
            return []

        video_arr = []
        origin_video_key = (
            note_item.get("video", {}).get("consumer", {}).get("origin_video_key", "")
        )
        if not origin_video_key:
            origin_video_key = (
                note_item.get("video", {}).get("consumer", {}).get("originVideoKey", "")
            )

        if not origin_video_key:
            videos = (
                note_item.get("video", {})
                .get("media", {})
                .get("stream", {})
                .get("h264", [])
            )
            if isinstance(videos, list):
                video_arr = [
                    v.get("master_url", "") for v in videos if v.get("master_url")
                ]
        else:
            video_arr = [f"http://sns-video-bd.xhscdn.com/{origin_video_key}"]

        return video_arr

    def extract_comments_from_dict(
        self,
        note_id: str,
        comments_data: List[Dict],
        note_xsec_token: str = "",
        root_comment_id: str = "",
    ) -> List[XhsComment]:
        """从API响应中提取评论列表

        Args:
            note_id: 笔记ID
            comments_data: 评论数据列表
            note_xsec_token: xsec_token
            root_comment_id: 根评论ID

        Returns:
            List[XhsComment]: 评论模型对象列表
        """
        if not comments_data:
            return []

        result = []
        for comment_item in comments_data:
            comment = self._extract_comment_from_dict(
                note_id, comment_item, note_xsec_token, root_comment_id
            )
            result.append(comment)
        return result

    def _extract_comment_from_dict(
        self,
        note_id: str,
        comment_item: Dict,
        note_xsec_token: str,
        root_comment_id: str = "",
    ) -> XhsComment:
        """内部方法：从字典提取评论信息"""
        user_info = comment_item.get("user_info", {})
        comment_pictures = [
            item.get("url_default", "") for item in comment_item.get("pictures", [])
        ]
        target_comment = comment_item.get("target_comment", {})

        return XhsComment(
            comment_id=comment_item.get("id", ""),
            parent_comment_id=root_comment_id,
            target_comment_id=target_comment.get("id", ""),
            note_id=note_id,
            content=comment_item.get("content", ""),
            create_time=str(comment_item.get("create_time", "")),
            ip_location=comment_item.get("ip_location", ""),
            sub_comment_count=str(comment_item.get("sub_comment_count", "0")),
            like_count=str(comment_item.get("like_count", "0")),
            pictures=",".join(comment_pictures),
            note_url=f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={note_xsec_token}&xsec_source=pc_search",
            user_id=user_info.get("user_id", ""),
            nickname=user_info.get("nickname", ""),
            avatar=user_info.get("image", ""),
        )

    def _extract_creator_from_dict(
        self, user_id: str, creator_data: Dict
    ) -> XhsCreator:
        """内部方法：从字典提取创作者信息"""
        if not creator_data:
            return XhsCreator(user_id=user_id)

        user_info = creator_data.get("basicInfo", {})

        follows = ""
        fans = ""
        interaction = ""
        for i in creator_data.get("interactions", []):
            if i.get("type") == "follows":
                follows = str(i.get("count", ""))
            elif i.get("type") == "fans":
                fans = str(i.get("count", ""))
            elif i.get("type") == "interaction":
                interaction = str(i.get("count", ""))

        return XhsCreator(
            user_id=user_id,
            nickname=user_info.get("nickname", ""),
            gender="女" if user_info.get("gender") == 1 else "男",
            avatar=user_info.get("images", ""),
            desc=user_info.get("desc", ""),
            ip_location=user_info.get("ipLocation", ""),
            follows=follows,
            fans=fans,
            interaction=interaction,
            tag_list=json.dumps(
                {
                    tag.get("tagType"): tag.get("name")
                    for tag in creator_data.get("tags", [])
                },
                ensure_ascii=False,
            ),
        )

    def parse_note_info_from_note_url(self, url: str) -> NoteUrlInfo:
        """
        从小红书笔记url中解析出笔记信息
        Args:
            url: "https://www.xiaohongshu.com/explore/66fad51c000000001b0224b8?xsec_token=AB3rO-QopW5sgrJ41GwN01WCXh6yWPxjSoFI9D5JIMgKw=&xsec_source=pc_search"
        Returns:

        """
        note_id = url.split("/")[-1].split("?")[0]
        params = extract_url_params_to_dict(url)
        xsec_token = params.get("xsec_token", "")
        xsec_source = params.get("xsec_source", "")
        return NoteUrlInfo(note_id=note_id, xsec_token=xsec_token, xsec_source=xsec_source)

    def parse_creator_info_from_creator_url(self, url: str) -> CreatorUrlInfo:
        """
        从小红书创作者主页url中解析出创作者信息

        Args:
            url (str): 创作者主页url

        Returns:
            CreatorUrlInfo: 创作者信息
        """
        creator_id = url.split("/")[-1].split("?")[0]
        params = extract_url_params_to_dict(url)
        xsec_token = params.get("xsec_token", "")
        xsec_source = params.get("xsec_source", "")
        return CreatorUrlInfo(
            creator_id=creator_id, xsec_token=xsec_token, xsec_source=xsec_source
        )
