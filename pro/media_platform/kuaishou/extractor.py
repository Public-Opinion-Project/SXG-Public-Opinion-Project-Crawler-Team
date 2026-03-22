# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/media_platform/kuaishou/extractor.py
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

from typing import Dict, List, Optional

from model.m_kuaishou import KuaishouVideo, KuaishouVideoComment, KuaishouCreator
from var import source_keyword_var


class KuaishouExtractor:
    """快手数据提取器"""

    def __init__(self):
        pass

    def extract_video_from_dict(self, video_data: Dict) -> Optional[KuaishouVideo]:
        """
        从API响应字典中提取视频信息

        Args:
            video_data: API响应的视频数据

        Returns:
            KuaishouVideo: 视频模型对象
        """
        if not video_data:
            return None

        photo_info = video_data.get("photo", {})
        video_id = photo_info.get("id")
        if not video_id:
            return None

        user_info = video_data.get("author", {})

        return KuaishouVideo(
            video_id=video_id,
            video_type=str(video_data.get("type", "")),
            title=photo_info.get("caption", "")[:500],
            desc=photo_info.get("caption", "")[:500],
            create_time=str(photo_info.get("timestamp", "")),
            liked_count=str(photo_info.get("realLikeCount", "")),
            viewd_count=str(photo_info.get("viewCount", "")),
            video_url=f"https://www.kuaishou.com/short-video/{video_id}",
            video_cover_url=photo_info.get("coverUrl", ""),
            video_play_url=photo_info.get("photoUrl", ""),
            source_keyword=source_keyword_var.get(),
            # 用户信息
            user_id=str(user_info.get("id", "")),
            nickname=user_info.get("name", ""),
            avatar=user_info.get("headerUrl", ""),
        )

    def extract_comment_from_dict(
        self,
        video_id: str,
        comment_data: Dict
    ) -> Optional[KuaishouVideoComment]:
        """
        从API响应字典中提取评论信息

        Args:
            video_id: 视频ID
            comment_data: API响应的评论数据

        Returns:
            KuaishouVideoComment: 评论模型对象
        """
        if not comment_data:
            return None

        comment_id = comment_data.get("commentId")
        if not comment_id:
            return None

        return KuaishouVideoComment(
            comment_id=comment_id,
            video_id=video_id,
            content=comment_data.get("content", ""),
            create_time=str(comment_data.get("timestamp", "")),
            sub_comment_count=str(comment_data.get("subCommentCount", 0)),
            like_count=str(
                comment_data.get("realLikedCount", 0)
                if comment_data.get("realLikedCount")
                else 0
            ),
            # 用户信息
            user_id=str(comment_data.get("authorId", "")),
            nickname=comment_data.get("authorName", ""),
            avatar=comment_data.get("headurl", ""),
        )

    def extract_comments_from_list(
        self,
        video_id: str,
        comments_data: List[Dict]
    ) -> List[KuaishouVideoComment]:
        """
        从API响应中提取评论列表

        Args:
            video_id: 视频ID
            comments_data: 评论数据列表

        Returns:
            List[KuaishouVideoComment]: 评论模型对象列表
        """
        if not comments_data:
            return []

        result = []
        for comment_item in comments_data:
            comment = self.extract_comment_from_dict(video_id, comment_item)
            if comment:
                result.append(comment)
        return result

    def extract_comment_from_dict_v2(
        self,
        video_id: str,
        comment_data: Dict
    ) -> Optional[KuaishouVideoComment]:
        """
        从V2 API响应字典中提取评论信息

        V2 API字段映射:
        - comment_id (number) -> comment_id (string)
        - author_id -> user_id
        - author_name -> nickname
        - likeCount -> like_count
        - commentCount -> sub_comment_count

        Args:
            video_id: 视频ID
            comment_data: V2 API响应的评论数据

        Returns:
            KuaishouVideoComment: 评论模型对象
        """
        if not comment_data:
            return None

        # V2 API的comment_id是number类型
        comment_id = comment_data.get("comment_id")
        if not comment_id:
            return None

        return KuaishouVideoComment(
            comment_id=str(comment_id),  # 转换为string保持一致
            video_id=video_id,
            content=comment_data.get("content", ""),
            create_time=str(comment_data.get("timestamp", "")),
            sub_comment_count=str(comment_data.get("commentCount", 0)),  # V2使用commentCount
            like_count=str(comment_data.get("likeCount", 0)),  # V2使用likeCount
            # 用户信息 - V2使用snake_case
            user_id=str(comment_data.get("author_id", "")),
            nickname=comment_data.get("author_name", ""),
            avatar=comment_data.get("headurl", ""),
        )

    def extract_comments_from_list_v2(
        self,
        video_id: str,
        comments_data: List[Dict]
    ) -> List[KuaishouVideoComment]:
        """
        从V2 API响应中提取评论列表

        Args:
            video_id: 视频ID
            comments_data: V2版本评论数据列表

        Returns:
            List[KuaishouVideoComment]: 评论模型对象列表
        """
        if not comments_data:
            return []

        result = []
        for comment_item in comments_data:
            comment = self.extract_comment_from_dict_v2(video_id, comment_item)
            if comment:
                result.append(comment)
        return result

    def extract_creator_from_dict(self, user_id: str, creator_data: Dict) -> Optional[KuaishouCreator]:
        """
        从API响应中提取创作者信息

        Args:
            user_id: 用户ID
            creator_data: 创作者数据

        Returns:
            KuaishouCreator: 创作者模型对象
        """
        if not creator_data:
            return None

        owner_count = creator_data.get("ownerCount", {})
        profile = creator_data.get("profile", {})

        return KuaishouCreator(
            user_id=user_id,
            nickname=profile.get("user_name", ""),
            gender="女" if profile.get("gender") == "F" else "男",
            avatar=profile.get("headurl", ""),
            desc=profile.get("user_text", ""),
            ip_location="",
            follows=str(owner_count.get("follow", "")),
            fans=str(owner_count.get("fan", "")),
            videos_count=str(owner_count.get("photo_public", "")),
        )
