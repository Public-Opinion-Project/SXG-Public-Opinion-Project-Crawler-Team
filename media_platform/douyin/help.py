# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/douyin/help.py
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
抖音辅助工具模块

提供抖音 API 签名参数生成和 URL 解析功能
包括 a_bogus 参数生成、视频/创作者 URL 解析等
"""

# -*- coding: utf-8 -*-
# @Author  : relakkes@gmail.com
# @Name: Programmer Ajiang-Relakkes
# @Time    : 2024/6/10 02:24
# @Desc    : 获取 a_bogus 参数，仅供学习交流使用，不得用于商业用途，如涉及侵权请联系作者删除

import random
import re
from typing import Optional

import execjs
from playwright.async_api import Page

from model.m_douyin import VideoUrlInfo, CreatorUrlInfo
from tools.crawler_util import extract_url_params_to_dict

# 编译抖音签名 JS 文件
douyin_sign_obj = execjs.compile(open('libs/douyin.js', encoding='utf-8-sig').read())

def get_web_id():
    """
    生成随机 web_id
    
    web_id 是抖音 API 所需的设备标识参数
    
    返回:
        生成的 web_id 字符串
    """

    def e(t):
        if t is not None:
            return str(t ^ (int(16 * random.random()) >> (t // 4)))
        else:
            return ''.join(
                [str(int(1e7)), '-', str(int(1e3)), '-', str(int(4e3)), '-', str(int(8e3)), '-', str(int(1e11))]
            )

    web_id = ''.join(
        e(int(x)) if x in '018' else x for x in e(None)
    )
    return web_id.replace('-', '')[:19]



async def get_a_bogus(url: str, params: str, post_data: dict, user_agent: str, page: Page = None):
    """
    获取 a_bogus 参数
    
    a_bogus 是抖音 API 的签名参数，用于验证请求合法性
    当前不支持 POST 请求类型的签名
    
    参数:
        url: API 请求 URL
        params: URL 查询参数字符串
        post_data: POST 请求数据字典
        user_agent: 用户代理字符串
        page: Playwright 页面对象（可选）
        
    返回:
        a_bogus 签名参数
    """
    return get_a_bogus_from_js(url, params, user_agent)

def get_a_bogus_from_js(url: str, params: str, user_agent: str):
    """
    通过 JS 脚本获取 a_bogus 参数
    
    参数:
        url: API 请求 URL
        params: URL 查询参数字符串
        user_agent: 用户代理字符串
        
    返回:
        a_bogus 签名参数
    """
    sign_js_name = "sign_datail"
    if "/reply" in url:
        sign_js_name = "sign_reply"
    return douyin_sign_obj.call(sign_js_name, params, user_agent)



async def get_a_bogus_from_playwright(params: str, post_data: dict, user_agent: str, page: Page):
    """
    通过 Playwright 获取 a_bogus 参数
    
    此版本已弃用
    
    参数:
        params: URL 查询参数字符串
        post_data: POST 请求数据字典
        user_agent: 用户代理字符串
        page: Playwright 页面对象
        
    返回:
        a_bogus 签名参数
    """
    if not post_data:
        post_data = ""
    a_bogus = await page.evaluate(
        "([params, post_data, ua]) => window.bdms.init._v[2].p[42].apply(null, [0, 1, 8, params, post_data, ua])",
        [params, post_data, user_agent])

    return a_bogus


def parse_video_info_from_url(url: str) -> VideoUrlInfo:
    """
    解析抖音视频 URL 获取视频 ID
    
    支持以下格式：
    1. 普通视频链接: https://www.douyin.com/video/7525082444551310602
    2. 带有 modal_id 参数的链接:
       - https://www.douyin.com/user/MS4wLjABAAAATJPY7LAlaa5X-c8uNdWkvz0jUGgpw4eeXIwu_8BhvqE?modal_id=7525082444551310602
       - https://www.douyin.com/root/search/python?modal_id=7471165520058862848
    3. 短链接: https://v.douyin.com/iF12345ABC/（需要客户端解析）
    4. 纯 ID: 7525082444551310602

    参数:
        url: 抖音视频链接或 ID
        
    返回:
        VideoUrlInfo: 包含视频 ID 的对象
        
    抛出:
        ValueError: 无法从 URL 解析视频 ID
    """
    # 如果是纯数字 ID，直接返回
    if url.isdigit():
        return VideoUrlInfo(aweme_id=url, url_type="normal")

    # 检查是否是短链接 (v.douyin.com)
    if "v.douyin.com" in url or url.startswith("http") and len(url) < 50 and "video" not in url:
        return VideoUrlInfo(aweme_id="", url_type="short")  # 需要客户端解析

    # 尝试从 URL 参数中提取 modal_id
    params = extract_url_params_to_dict(url)
    modal_id = params.get("modal_id")
    if modal_id:
        return VideoUrlInfo(aweme_id=modal_id, url_type="modal")

    # 从标准视频 URL 中提取 ID: /video/number
    video_pattern = r'/video/(\d+)'
    match = re.search(video_pattern, url)
    if match:
        aweme_id = match.group(1)
        return VideoUrlInfo(aweme_id=aweme_id, url_type="normal")

    raise ValueError(f"无法从 URL 解析视频 ID: {url}")


def parse_creator_info_from_url(url: str) -> CreatorUrlInfo:
    """
    解析抖音创作者主页 URL 获取创作者 ID (sec_user_id)
    
    支持以下格式：
    1. 创作者主页: https://www.douyin.com/user/MS4wLjABAAAATJPY7LAlaa5X-c8uNdWkvz0jUGgpw4eeXIwu_8BhvqE?from_tab_name=main
    2. 纯 ID: MS4wLjABAAAATJPY7LAlaa5X-c8uNdWkvz0jUGgpw4eeXIwu_8BhvqE

    参数:
        url: 抖音创作者主页链接或 sec_user_id
        
    返回:
        CreatorUrlInfo: 包含创作者 ID 的对象
        
    抛出:
        ValueError: 无法从 URL 解析创作者 ID
    """
    # 如果是纯 ID 格式（通常以 MS4wLjABAAAA 开头），直接返回
    if url.startswith("MS4wLjABAAAA") or (not url.startswith("http") and "douyin.com" not in url):
        return CreatorUrlInfo(sec_user_id=url)

    # 从创作者主页 URL 中提取 sec_user_id: /user/xxx
    user_pattern = r'/user/([^/?]+)'
    match = re.search(user_pattern, url)
    if match:
        sec_user_id = match.group(1)
        return CreatorUrlInfo(sec_user_id=sec_user_id)

    raise ValueError(f"无法从 URL 解析创作者 ID: {url}")


if __name__ == '__main__':
    # Test video URL parsing
    print("=== Video URL Parsing Test ===")
    test_urls = [
        "https://www.douyin.com/video/7525082444551310602",
        "https://www.douyin.com/user/MS4wLjABAAAATJPY7LAlaa5X-c8uNdWkvz0jUGgpw4eeXIwu_8BhvqE?from_tab_name=main&modal_id=7525082444551310602",
        "https://www.douyin.com/root/search/python?aid=b733a3b0-4662-4639-9a72-c2318fba9f3f&modal_id=7471165520058862848&type=general",
        "7525082444551310602",
    ]
    for url in test_urls:
        try:
            result = parse_video_info_from_url(url)
            print(f"✓ URL: {url[:80]}...")
            print(f"  Result: {result}\n")
        except Exception as e:
            print(f"✗ URL: {url}")
            print(f"  Error: {e}\n")

    # Test creator URL parsing
    print("=== Creator URL Parsing Test ===")
    test_creator_urls = [
        "https://www.douyin.com/user/MS4wLjABAAAATJPY7LAlaa5X-c8uNdWkvz0jUGgpw4eeXIwu_8BhvqE?from_tab_name=main",
        "MS4wLjABAAAATJPY7LAlaa5X-c8uNdWkvz0jUGgpw4eeXIwu_8BhvqE",
    ]
    for url in test_creator_urls:
        try:
            result = parse_creator_info_from_url(url)
            print(f"✓ URL: {url[:80]}...")
            print(f"  Result: {result}\n")
        except Exception as e:
            print(f"✗ URL: {url}")
            print(f"  Error: {e}\n")
