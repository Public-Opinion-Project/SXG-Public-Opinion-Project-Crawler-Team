# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/bilibili/extractor.py
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
import urllib.parse
from typing import Dict, List, Optional

from model.m_bilibili import BilibiliVideo, BilibiliComment, BilibiliUpInfo
from var import source_keyword_var


class BilibiliExtractor:
    """Bilibili数据提取器"""

    def __init__(self):
        pass

    def extract_video_from_dict(self, video_data: Dict) -> Optional[BilibiliVideo]:
        """
        从API响应字典中提取视频信息

        Args:
            video_data: API响应的视频数据

        Returns:
            BilibiliVideo: 视频模型对象
        """
        if not video_data:
            return None

        # 提取统计信息
        stat = video_data.get("stat", {})
        owner = video_data.get("owner", {})

        return BilibiliVideo(
            video_id=str(video_data.get("aid", "")),
            bvid=video_data.get("bvid", ""),
            video_type=video_data.get("tname", ""),
            title=video_data.get("title", ""),
            desc=video_data.get("desc", ""),
            create_time=str(video_data.get("pubdate", "")),
            duration=str(video_data.get("duration", "")),

            # 统计信息
            liked_count=str(stat.get("like", "")),
            video_play_count=str(stat.get("view", "")),
            video_danmaku=str(stat.get("danmaku", "")),
            video_comment=str(stat.get("reply", "")),

            # 视频链接
            video_url=f"https://www.bilibili.com/video/{video_data.get('bvid', '')}",
            video_cover_url=video_data.get("pic", ""),

            # 作者信息
            user_id=str(owner.get("mid", "")),
            nickname=owner.get("name", ""),
            avatar=owner.get("face", ""),

            # 其他信息
            source_keyword=source_keyword_var.get()
        )

    def extract_comments_from_dict(self, video_id: str, comments_data: List[Dict]) -> List[BilibiliComment]:
        """
        从API响应中提取评论列表

        Args:
            video_id: 视频ID
            comments_data: 评论数据列表

        Returns:
            List[BilibiliComment]: 评论模型对象列表
        """
        if not comments_data:
            return []

        result = []
        for comment_item in comments_data:
            comment = self._extract_comment_from_dict(video_id, comment_item)
            if comment:
                result.append(comment)
        return result

    def _extract_comment_from_dict(self, video_id: str, comment_item: Dict) -> Optional[BilibiliComment]:
        """内部方法：从字典提取评论信息"""
        if not comment_item:
            return None

        member = comment_item.get("member", {})

        return BilibiliComment(
            comment_id=str(comment_item.get("rpid", "")),
            video_id=str(video_id),
            content=comment_item.get("content", {}).get("message", ""),
            create_time=str(comment_item.get("ctime", "")),

            # 统计信息
            sub_comment_count=str(comment_item.get("rcount", "")),
            like_count=str(comment_item.get("like", "")),

            # 评论关系
            parent_comment_id=str(comment_item.get("parent", "") or ""),

            # 用户信息
            user_id=str(member.get("mid", "")),
            nickname=member.get("uname", ""),
            avatar=member.get("avatar", "")
        )

    def extract_up_info_from_dict(self, user_data: Dict) -> Optional[BilibiliUpInfo]:
        """
        从API响应中提取UP主信息

        Args:
            user_data: 用户数据

        Returns:
            BilibiliUpInfo: UP主信息模型对象
        """
        if not user_data:
            return None

        return BilibiliUpInfo(
            user_id=str(user_data.get("mid", "")),
            nickname=user_data.get("name", ""),
            avatar=user_data.get("face", ""),
            description=user_data.get("sign", ""),

            # 统计信息
            follower_count=str(user_data.get("follower", "0")),
            following_count=str(user_data.get("following", "0")),
            content_count=str(user_data.get("archive_count", "0"))
        )

    def extract_w_webid(self, html: str) -> str:
        """
        提取w_webid

        Args:
            html (str): B站主页HTML

        Returns:
            str: w_webid
        """
        __RENDER_DATA__ = re.search(
            r"<script id=\"__RENDER_DATA__\" type=\"application/json\">(.*?)</script>",
            html,
            re.S,
        ).group(1)
        w_webid = json.loads(urllib.parse.unquote(__RENDER_DATA__))["access_id"]
        return w_webid
