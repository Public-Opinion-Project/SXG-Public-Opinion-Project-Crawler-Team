# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/weibo/extractor.py
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

import re
from typing import Dict, List, Optional

from model.m_weibo import WeiboNote, WeiboComment, WeiboCreator
from pkg.tools import utils
from var import source_keyword_var


class WeiboExtractor:
    """微博数据提取器"""

    def __init__(self):
        pass

    def _get_video_url_arr(self, mblog: Dict) -> List[str]:
        """
        获取微博笔记的多个视频地址

        Args:
            mblog: 微博笔记数据

        Returns:
            List[str]: 多个视频地址
        """
        res_video_url_arr: List[str] = []
        page_info: Dict = mblog.get("page_info", {})
        many_quality_keys = ["mp4_720p_mp4", "mp4_hd_mp4", "mp4_ld_mp4"]
        if page_info.get("type") == "video":
            urls: Dict = page_info.get("urls", {})
            for key in many_quality_keys:
                if urls.get(key):
                    res_video_url_arr.append(urls.get(key))
        return res_video_url_arr

    def _get_image_list_arr(self, mblog: Dict) -> List[str]:
        """
        获取微博笔记的多个封面图片地址

        Args:
            mblog: 微博笔记数据

        Returns:
            List[str]: 多个封面图片地址
        """
        res_image_list_arr: List[str] = []
        pics: List[Dict] = mblog.get("pics", [])
        for pic in pics:
            if pic.get("url"):
                res_image_list_arr.append(pic.get("url"))
        return res_image_list_arr

    def extract_note_from_dict(self, note_data: Dict) -> Optional[WeiboNote]:
        """
        从API响应字典中提取微博笔记信息

        Args:
            note_data: API响应的笔记数据

        Returns:
            WeiboNote: 笔记模型对象
        """
        if not note_data:
            return None

        mblog: Dict = note_data.get("mblog", note_data)
        user_info: Dict = mblog.get("user", {})

        # 清理HTML标签
        content_text = mblog.get("text", "")
        clean_text = re.sub(r"<.*?>", "", content_text)

        # 获取图片和视频
        image_list = self._get_image_list_arr(mblog)
        video_url = self._get_video_url_arr(mblog)

        note_id = mblog.get("id", "")

        return WeiboNote(
            note_id=str(note_id),
            content=clean_text,
            create_time=str(utils.rfc2822_to_timestamp(mblog.get("created_at", ""))),
            create_date_time=str(utils.rfc2822_to_china_datetime(mblog.get("created_at", ""))),
            liked_count=str(mblog.get("attitudes_count", 0)),
            comments_count=str(mblog.get("comments_count", 0)),
            shared_count=str(mblog.get("reposts_count", 0)),
            note_url=f"https://m.weibo.cn/detail/{note_id}",
            ip_location=mblog.get("region_name", "").replace("发布于 ", ""),

            # 媒体信息
            image_list=",".join(image_list),
            video_url=",".join(video_url),

            # 用户信息
            user_id=str(user_info.get("id", "")),
            nickname=user_info.get("screen_name", ""),
            gender=user_info.get("gender", ""),
            profile_url=user_info.get("profile_url", ""),
            avatar=user_info.get("profile_image_url", ""),

            # 其他信息
            source_keyword=source_keyword_var.get()
        )

    def extract_comment_from_dict(self, note_id: str, comment_data: Dict) -> Optional[WeiboComment]:
        """
        从API响应字典中提取微博评论信息

        Args:
            note_id: 笔记ID
            comment_data: API响应的评论数据

        Returns:
            WeiboComment: 评论模型对象
        """
        if not comment_data:
            return None

        user_info: Dict = comment_data.get("user", {})

        # 清理HTML标签
        content_text = comment_data.get("text", "")
        clean_text = re.sub(r"<.*?>", "", content_text)

        # 处理子评论
        sub_comments = None
        if comment_data.get("comments") and isinstance(comment_data.get("comments"), list):
            sub_comments = []
            for sub_comment_data in comment_data.get("comments", []):
                sub_comment = self.extract_comment_from_dict(note_id, sub_comment_data)
                if sub_comment:
                    sub_comments.append(sub_comment)

        return WeiboComment(
            comment_id=str(comment_data.get("id", "")),
            note_id=str(note_id),
            content=clean_text,
            create_time=str(utils.rfc2822_to_timestamp(comment_data.get("created_at", ""))),
            create_date_time=str(utils.rfc2822_to_china_datetime(comment_data.get("created_at", ""))),
            sub_comment_count=str(comment_data.get("total_number", 0)),
            like_count=str(comment_data.get("like_count", 0)),
            ip_location=comment_data.get("source", "").replace("来自", ""),
            parent_comment_id=str(comment_data.get("rootid", "") or ""),

            # 用户信息
            user_id=str(user_info.get("id", "")),
            nickname=user_info.get("screen_name", ""),
            gender=user_info.get("gender", ""),
            profile_url=user_info.get("profile_url", ""),
            avatar=user_info.get("profile_image_url", ""),

            # 子评论
            sub_comments=sub_comments
        )

    def extract_comments_from_list(self, note_id: str, comments_data: List[Dict]) -> List[WeiboComment]:
        """
        从API响应中提取评论列表

        Args:
            note_id: 笔记ID
            comments_data: 评论数据列表

        Returns:
            List[WeiboComment]: 评论模型对象列表
        """
        if not comments_data:
            return []

        result = []
        for comment_item in comments_data:
            comment = self.extract_comment_from_dict(note_id, comment_item)
            if comment:
                result.append(comment)
        return result

    def extract_creator_from_dict(self, user_data: Dict) -> Optional[WeiboCreator]:
        """
        从API响应中提取创作者信息

        Args:
            user_data: 用户数据

        Returns:
            WeiboCreator: 创作者模型对象
        """
        if not user_data:
            return None

        return WeiboCreator(
            user_id=str(user_data.get("id", "")),
            nickname=user_data.get("screen_name", ""),
            gender="女" if user_data.get("gender") == "f" else "男",
            avatar=user_data.get("avatar_hd", ""),
            desc=user_data.get("description", ""),
            ip_location=user_data.get("source", "").replace("来自", ""),
            follows=str(user_data.get("follow_count", "")),
            fans=str(user_data.get("followers_count", "")),
            tag_list=""
        )
