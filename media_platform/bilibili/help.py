# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/bilibili/help.py
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
哔哩哔哩平台辅助函数模块

提供请求参数签名和 URL 解析等辅助功能
签名算法基于逆向工程实现，参考：https://socialsisteryi.github.io/bilibili-API-collect/docs/misc/sign/wbi.html#wbi签名算法
"""

import re
import urllib.parse
from hashlib import md5
from typing import Dict

from model.m_bilibili import VideoUrlInfo, CreatorUrlInfo
from tools import utils


class BilibiliSign:
    """
    哔哩哔哩请求参数签名类

    用于生成 Bilibili WBI 签名
    需要从网页的 localStorage 中获取 img_key 和 sub_key
    """

    def __init__(self, img_key: str, sub_key: str):
        """
        初始化签名类

        参数:
            img_key: 从 localStorage 获取的 wbi_img_urls 中的图片 key
            sub_key: 从 localStorage 获取的 wbi_img_urls 中的子 key
        """
        self.img_key = img_key
        self.sub_key = sub_key
        # 映射表，用于从 mixin_key 中提取字符
        self.map_table = [
            46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
            33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
            61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
            36, 20, 34, 44, 52
        ]

    def get_salt(self) -> str:
        """
        获取盐值密钥

        将 img_key 和 sub_key 拼接后，根据映射表提取前32位字符作为盐值

        返回:
            str: 32位的盐值字符串
        """
        salt = ""
        mixin_key = self.img_key + self.sub_key
        for mt in self.map_table:
            salt += mixin_key[mt]
        return salt[:32]

    def sign(self, req_data: Dict) -> Dict:
        """
        对请求参数进行签名

        处理步骤：
        1. 将当前时间戳添加到请求参数中
        2. 按字典键排序
        3. URL 编码参数
        4. 拼接盐值生成 MD5 签名（w_rid 参数）

        参数:
            req_data: 原始请求参数字典

        返回:
            包含签名的请求参数字典
        """
        # 添加时间戳
        current_ts = utils.get_unix_timestamp()
        req_data.update({"wts": current_ts})
        # 按键排序
        req_data = dict(sorted(req_data.items()))
        # 过滤掉 "!'()*" 字符
        req_data = {
            k: ''.join(filter(lambda ch: ch not in "!'()*", str(v)))
            for k, v
            in req_data.items()
        }
        # URL 编码
        query = urllib.parse.urlencode(req_data)
        # 获取盐值
        salt = self.get_salt()
        # 计算 w_rid 签名
        wbi_sign = md5((query + salt).encode()).hexdigest()
        req_data['w_rid'] = wbi_sign
        return req_data


def parse_video_info_from_url(url: str) -> VideoUrlInfo:
    """
    从哔哩哔哩视频 URL 中解析视频 ID

    参数:
        url: 哔哩哔哩视频链接，支持以下格式：
            - https://www.bilibili.com/video/BV1dwuKzmE26/?spm_id_from=333.1387.homepage.video_card.click
            - https://www.bilibili.com/video/BV1d54y1g7db
            - BV1d54y1g7db（直接传入 BV 号）

    返回:
        VideoUrlInfo: 包含视频 ID 的对象

    异常:
        ValueError: 无法从 URL 中解析出视频 ID 时抛出
    """
    # 如果输入已经是 BV 号，直接返回
    if url.startswith("BV"):
        return VideoUrlInfo(video_id=url)

    # 使用正则表达式提取 BV 号
    # 匹配 /video/BV... 格式
    bv_pattern = r'/video/(BV[a-zA-Z0-9]+)'
    match = re.search(bv_pattern, url)

    if match:
        video_id = match.group(1)
        return VideoUrlInfo(video_id=video_id)

    raise ValueError(f"Unable to parse video ID from URL: {url}")


def parse_creator_info_from_url(url: str) -> CreatorUrlInfo:
    """
    从哔哩哔哩创作者空间 URL 中解析创作者 ID

    参数:
        url: 哔哩哔哩创作者空间链接，支持以下格式：
            - https://space.bilibili.com/434377496?spm_id_from=333.1007.0.0
            - https://space.bilibili.com/20813884
            - 434377496（直接传入 UID）

    返回:
        CreatorUrlInfo: 包含创作者 ID 的对象

    异常:
        ValueError: 无法从 URL 中解析出创作者 ID 时抛出
    """
    # 如果输入已经是数字 ID，直接返回
    if url.isdigit():
        return CreatorUrlInfo(creator_id=url)

    # 使用正则表达式提取 UID
    # 匹配 /space.bilibili.com/number 格式
    uid_pattern = r'space\.bilibili\.com/(\d+)'
    match = re.search(uid_pattern, url)

    if match:
        creator_id = match.group(1)
        return CreatorUrlInfo(creator_id=creator_id)

    raise ValueError(f"Unable to parse creator ID from URL: {url}")


if __name__ == '__main__':
    # 测试视频 URL 解析
    video_url1 = "https://www.bilibili.com/video/BV1dwuKzmE26/?spm_id_from=333.1387.homepage.video_card.click"
    video_url2 = "BV1d54y1g7db"
    print("Video URL parsing test:")
    print(f"URL1: {video_url1} -> {parse_video_info_from_url(video_url1)}")
    print(f"URL2: {video_url2} -> {parse_video_info_from_url(video_url2)}")

    # 测试创作者 URL 解析
    creator_url1 = "https://space.bilibili.com/434377496?spm_id_from=333.1007.0.0"
    creator_url2 = "20813884"
    print("\nCreator URL parsing test:")
    print(f"URL1: {creator_url1} -> {parse_creator_info_from_url(creator_url1)}")
    print(f"URL2: {creator_url2} -> {parse_creator_info_from_url(creator_url2)}")
