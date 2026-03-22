# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/douyin/login.py
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
抖音登录模块

提供抖音平台的登录实现
支持二维码登录、手机验证码登录、Cookie 登录三种方式
包含滑块验证处理
"""

import asyncio
import functools
import sys
from typing import Optional

from playwright.async_api import BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from tenacity import (RetryError, retry, retry_if_result, stop_after_attempt,
                      wait_fixed)

import config
from base.base_crawler import AbstractLogin
from cache.cache_factory import CacheFactory
from tools import utils


class DouYinLogin(AbstractLogin):
    """
    抖音登录类
    
    负责处理抖音平台的登录流程
    支持二维码登录、手机验证码登录、Cookie 登录三种方式
    
    属性:
        browser_context: Playwright 浏览器上下文
        context_page: Playwright 页面对象
        login_phone: 登录手机号
        scan_qrcode_time: 二维码扫描超时时间
        cookie_str: Cookie 字符串
    """

    def __init__(self,
                 login_type: str,
                 browser_context: BrowserContext, # type: ignore
                 context_page: Page, # type: ignore
                 login_phone: Optional[str] = "",
                 cookie_str: Optional[str] = ""
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
        self.scan_qrcode_time = 60
        self.cookie_str = cookie_str

    async def begin(self):
        """
        开始登录流程
        
        入口函数，根据配置选择登录方式并执行登录
        滑块验证精度不太好...如果没有特殊要求，建议不使用抖音登录，或使用 Cookie 登录
        """

        # 弹出登录对话框
        await self.popup_login_dialog()

        # 选择登录方式
        if config.LOGIN_TYPE == "qrcode":
            await self.login_by_qrcode()
        elif config.LOGIN_TYPE == "phone":
            await self.login_by_mobile()
        elif config.LOGIN_TYPE == "cookie":
            await self.login_by_cookies()
        else:
            raise ValueError("[DouYinLogin.begin] 无效的登录类型，目前只支持 qrcode、phone 或 cookie ...")

        # 如果页面重定向到滑块验证页面，需要再次滑动
        await asyncio.sleep(6)
        current_page_title = await self.context_page.title()
        if "验证码中间页" in current_page_title:
            await self.check_page_display_slider(move_step=3, slider_level="hard")

        # 检查登录状态
        utils.logger.info(f"[DouYinLogin.begin] 登录完成，开始检查登录状态 ...")
        try:
            await self.check_login_state()
        except RetryError:
            utils.logger.info("[DouYinLogin.begin] 登录失败，请确认 ...")
            sys.exit()

        # 等待重定向
        wait_redirect_seconds = 5
        utils.logger.info(f"[DouYinLogin.begin] 登录成功，等待 {wait_redirect_seconds} 秒后重定向 ...")
        await asyncio.sleep(wait_redirect_seconds)

    @retry(stop=stop_after_attempt(600), wait=wait_fixed(1), retry=retry_if_result(lambda value: value is False))
    async def check_login_state(self):
        """
        检查当前登录状态
        
        通过 localStorage 和 Cookie 判断用户是否登录成功
        
        返回:
            True 表示已登录，False 表示未登录
        """
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = utils.convert_cookies(current_cookie)

        for page in self.browser_context.pages:
            try:
                local_storage = await page.evaluate("() => window.localStorage")
                if local_storage.get("HasUserLogin", "") == "1":
                    return True
            except Exception as e:
                # utils.logger.warn(f"[DouYinLogin] check_login_state waring: {e}")
                await asyncio.sleep(0.1)

        if cookie_dict.get("LOGIN_STATUS") == "1":
            return True

        return False

    async def popup_login_dialog(self):
        """
        弹出登录对话框
        
        如果登录对话框没有自动弹出，则手动点击登录按钮
        """
        dialog_selector = "xpath=//div[@id='login-panel-new']"
        try:
            # 检查对话框是否自动弹出，等待10秒
            await self.context_page.wait_for_selector(dialog_selector, timeout=1000 * 10)
        except Exception as e:
            utils.logger.error(f"[DouYinLogin.popup_login_dialog] 登录对话框未自动弹出，错误: {e}")
            utils.logger.info("[DouYinLogin.popup_login_dialog] 登录对话框未自动弹出，将手动点击登录按钮")
            login_button_ele = self.context_page.locator("xpath=//p[text() = '登录']")
            await login_button_ele.click()
            await asyncio.sleep(0.5)

    async def login_by_qrcode(self):
        """
        二维码登录
        
        获取二维码并在终端显示，等待用户扫描
        """
        utils.logger.info("[DouYinLogin.login_by_qrcode] 开始二维码登录 ...")
        qrcode_img_selector = "xpath=//div[@id='animate_qrcode_container']//img"
        base64_qrcode_img = await utils.find_login_qrcode(
            self.context_page,
            selector=qrcode_img_selector
        )
        if not base64_qrcode_img:
            utils.logger.info("[DouYinLogin.login_by_qrcode] 未找到登录二维码，请确认 ...")
            sys.exit()

        partial_show_qrcode = functools.partial(utils.show_qrcode, base64_qrcode_img)
        asyncio.get_running_loop().run_in_executor(executor=None, func=partial_show_qrcode)
        await asyncio.sleep(2)

    async def login_by_mobile(self):
        """
        手机验证码登录
        
        输入手机号，获取并填写验证码
        """
        utils.logger.info("[DouYinLogin.login_by_mobile] 开始手机验证码登录 ...")
        mobile_tap_ele = self.context_page.locator("xpath=//li[text() = '验证码登录']")
        await mobile_tap_ele.click()
        await self.context_page.wait_for_selector("xpath=//article[@class='web-login-mobile-code']")
        mobile_input_ele = self.context_page.locator("xpath=//input[@placeholder='手机号']")
        await mobile_input_ele.fill(self.login_phone)
        await asyncio.sleep(0.5)
        send_sms_code_btn = self.context_page.locator("xpath=//span[text() = '获取验证码']")
        await send_sms_code_btn.click()

        # 检查是否有滑块验证
        await self.check_page_display_slider(move_step=10, slider_level="easy")
        cache_client = CacheFactory.create_cache(config.CACHE_TYPE_MEMORY)
        max_get_sms_code_time = 60 * 2  # 获取验证码最长时间为2分钟
        while max_get_sms_code_time > 0:
            utils.logger.info(f"[DouYinLogin.login_by_mobile] 从redis获取抖音验证码，剩余时间 {max_get_sms_code_time}s ...")
            await asyncio.sleep(1)
            sms_code_key = f"dy_{self.login_phone}"
            sms_code_value = cache_client.get(sms_code_key)
            if not sms_code_value:
                max_get_sms_code_time -= 1
                continue

            sms_code_input_ele = self.context_page.locator("xpath=//input[@placeholder='请输入验证码']")
            await sms_code_input_ele.fill(value=sms_code_value.decode())
            await asyncio.sleep(0.5)
            submit_btn_ele = self.context_page.locator("xpath=//button[@class='web-login-button']")
            await submit_btn_ele.click()  # 点击登录
            # todo ... 还应该检查验证码是否正确，可能不正确
            break

    async def check_page_display_slider(self, move_step: int = 10, slider_level: str = "easy"):
        """
        检查页面是否出现滑块验证
        
        如果出现滑块验证，则自动完成验证
        
        参数:
            move_step: 移动步长，控制单次移动速度比例
            slider_level: 滑块难度，easy（简单）或 hard（困难）
        """
        # 等待滑块验证出现
        back_selector = "#captcha-verify-image"
        try:
            await self.context_page.wait_for_selector(selector=back_selector, state="visible", timeout=30 * 1000)
        except PlaywrightTimeoutError:  # 没有滑块验证，直接返回
            return

        gap_selector = 'xpath=//*[@id="captcha_container"]/div/div[2]/img[2]'
        max_slider_try_times = 20
        slider_verify_success = False
        while not slider_verify_success:
            if max_slider_try_times <= 0:
                utils.logger.error("[DouYinLogin.check_page_display_slider] 滑块验证失败 ...")
                sys.exit()
            try:
                await self.move_slider(back_selector, gap_selector, move_step, slider_level)
                await asyncio.sleep(1)

                # 如果滑动太慢或验证失败，会提示"操作过慢"，这里点击刷新按钮
                page_content = await self.context_page.content()
                if "操作过慢" in page_content or "提示重新操作" in page_content:
                    utils.logger.info("[DouYinLogin.check_page_display_slider] 滑块验证失败，重试 ...")
                    await self.context_page.click(selector="//a[contains(@class, 'secsdk_captcha_refresh')]")
                    continue

                # 滑动成功后，等待滑块消失
                await self.context_page.wait_for_selector(selector=back_selector, state="hidden", timeout=1000)
                # 如果滑块消失，说明验证成功，退出循环；否则说明验证失败，上面一行会抛异常被捕获继续循环
                utils.logger.info("[DouYinLogin.check_page_display_slider] 滑块验证成功 ...")
                slider_verify_success = True
            except Exception as e:
                utils.logger.error(f"[DouYinLogin.check_page_display_slider] 滑块验证失败，错误: {e}")
                await asyncio.sleep(1)
                max_slider_try_times -= 1
                utils.logger.info(f"[DouYinLogin.check_page_display_slider] 剩余滑块尝试次数: {max_slider_try_times}")
                continue

    async def move_slider(self, back_selector: str, gap_selector: str, move_step: int = 10, slider_level="easy"):
        """
        移动滑块完成验证
        
        参数:
            back_selector: 滑块验证背景图选择器
            gap_selector: 滑块验证滑块选择器
            move_step: 控制单次移动速度比例，默认为1，意思是无论距离多远都在0.1秒内移动完成，值越大越慢
            slider_level: 滑块难度 easy（手机验证码滑块）hard（验证码中间页滑块）
        """

        # 获取滑块背景图
        slider_back_elements = await self.context_page.wait_for_selector(
            selector=back_selector,
            timeout=1000 * 10,  # 等待10秒
        )
        slide_back = str(await slider_back_elements.get_property("src")) # type: ignore

        # 获取滑块缺口图
        gap_elements = await self.context_page.wait_for_selector(
            selector=gap_selector,
            timeout=1000 * 10,  # 等待10秒
        )
        gap_src = str(await gap_elements.get_property("src")) # type: ignore

        # 识别滑块位置
        slide_app = utils.Slide(gap=gap_src, bg=slide_back)
        distance = slide_app.discern()

        # 获取移动轨迹
        tracks = utils.get_tracks(distance, slider_level)
        new_1 = tracks[-1] - (sum(tracks) - distance)
        tracks.pop()
        tracks.append(new_1)

        # 根据轨迹拖动滑块到指定位置
        element = await self.context_page.query_selector(gap_selector)
        bounding_box = await element.bounding_box() # type: ignore

        await self.context_page.mouse.move(bounding_box["x"] + bounding_box["width"] / 2, # type: ignore
                                           bounding_box["y"] + bounding_box["height"] / 2) # type: ignore
        # 获取 x 坐标中心位置
        x = bounding_box["x"] + bounding_box["width"] / 2 # type: ignore
        # 模拟滑动操作
        await element.hover() # type: ignore
        await self.context_page.mouse.down()

        for track in tracks:
            # 根据轨迹循环移动鼠标
            # steps 控制单次移动速度比例，默认为1，意思是无论距离多远都在0.1秒内移动完成，值越大越慢
            await self.context_page.mouse.move(x + track, 0, steps=move_step)
            x += track
        await self.context_page.mouse.up()

    async def login_by_cookies(self):
        """
        Cookie 登录
        
        直接通过添加 Cookie 实现登录
        """
        utils.logger.info("[DouYinLogin.login_by_cookies] 开始 Cookie 登录 ...")
        for key, value in utils.convert_str_cookie_to_dict(self.cookie_str).items():
            await self.browser_context.add_cookies([{
                'name': key,
                'value': value,
                'domain': ".douyin.com",
                'path': "/"
            }])
