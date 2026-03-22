# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/kuaishou/login.py
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
快手登录模块

提供快手平台的登录实现
支持二维码登录、手机验证码登录、Cookie 登录三种方式
"""

import asyncio
import functools
import sys
from typing import Optional

from playwright.async_api import BrowserContext, Page
from tenacity import (RetryError, retry, retry_if_result, stop_after_attempt,
                      wait_fixed)

import config
from base.base_crawler import AbstractLogin
from tools import utils


class KuaishouLogin(AbstractLogin):
    """
    快手登录类
    
    负责处理快手平台的登录流程
    支持二维码登录、手机验证码登录、Cookie 登录三种方式
    
    属性:
        browser_context: Playwright 浏览器上下文
        context_page: Playwright 页面对象
        login_phone: 登录手机号
        cookie_str: Cookie 字符串
    """
    def __init__(self,
                 login_type: str,
                 browser_context: BrowserContext,
                 context_page: Page,
                 login_phone: Optional[str] = "",
                 cookie_str: str = ""
                 ):
        """
        初始化登录类
        
        参数:
            login_type: 登录类型，支持 qrcode（二维码）、phone（手机验证码）、cookie（Cookie）
            browser_context: Playwright 浏览器上下文
            context_page: Playwright 页面对象
            login_phone: 手机号码（手机验证码登录时使用）
            cookie_str: Cookie 字符串（Cookie 登录时使用）
        """
        config.LOGIN_TYPE = login_type
        self.browser_context = browser_context
        self.context_page = context_page
        self.login_phone = login_phone
        self.cookie_str = cookie_str

    async def begin(self):
        """
        开始登录流程
        
        入口函数，根据配置选择登录方式并执行登录
        """
        utils.logger.info("[KuaishouLogin.begin] 开始登录快手 ...")
        if config.LOGIN_TYPE == "qrcode":
            await self.login_by_qrcode()
        elif config.LOGIN_TYPE == "phone":
            await self.login_by_mobile()
        elif config.LOGIN_TYPE == "cookie":
            await self.login_by_cookies()
        else:
            raise ValueError("[KuaishouLogin.begin] 无效的登录类型，目前只支持 qrcode、phone 或 cookie ...")

    @retry(stop=stop_after_attempt(600), wait=wait_fixed(1), retry=retry_if_result(lambda value: value is False))
    async def check_login_state(self) -> bool:
        """
        检查当前登录状态
        
        通过 Cookie 判断用户是否登录成功
        重试装饰器会在返回值为 False 时重试 600 次，重试间隔为 1 秒
        达到最大重试次数后抛出 RetryError
        
        返回:
            True 表示已登录，False 表示未登录
        """
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = utils.convert_cookies(current_cookie)
        kuaishou_pass_token = cookie_dict.get("passToken")
        if kuaishou_pass_token:
            return True
        return False

    async def login_by_qrcode(self):
        """
        二维码登录
        
        获取二维码并在终端显示，等待用户扫描
        """
        utils.logger.info("[KuaishouLogin.login_by_qrcode] 开始二维码登录 ...")

        # 点击登录按钮
        login_button_ele = self.context_page.locator(
            "xpath=//p[text()='登录']"
        )
        await login_button_ele.click()

        # 查找登录二维码
        qrcode_img_selector = "//div[@class='qrcode-img']//img"
        base64_qrcode_img = await utils.find_login_qrcode(
            self.context_page,
            selector=qrcode_img_selector
        )
        if not base64_qrcode_img:
            utils.logger.info("[KuaishouLogin.login_by_qrcode] 登录失败，未找到二维码，请检查 ....")
            sys.exit()


        # 显示登录二维码
        partial_show_qrcode = functools.partial(utils.show_qrcode, base64_qrcode_img)
        asyncio.get_running_loop().run_in_executor(executor=None, func=partial_show_qrcode)

        utils.logger.info(f"[KuaishouLogin.login_by_qrcode] 等待扫码登录，剩余时间为 20s")
        try:
            await self.check_login_state()
        except RetryError:
            utils.logger.info("[KuaishouLogin.login_by_qrcode] 二维码登录方式登录快手失败 ...")
            sys.exit()

        wait_redirect_seconds = 5
        utils.logger.info(f"[KuaishouLogin.login_by_qrcode] 登录成功，等待 {wait_redirect_seconds} 秒后重定向 ...")
        await asyncio.sleep(wait_redirect_seconds)

    async def login_by_mobile(self):
        """
        手机验证码登录
        
        （暂未实现）
        """
        pass

    async def login_by_cookies(self):
        """
        Cookie 登录
        
        直接通过添加 Cookie 实现登录
        """
        utils.logger.info("[KuaishouLogin.login_by_cookies] 开始 Cookie 登录 ...")
        for key, value in utils.convert_str_cookie_to_dict(self.cookie_str).items():
            await self.browser_context.add_cookies([{
                'name': key,
                'value': value,
                'domain': ".kuaishou.com",
                'path': "/"
            }])
