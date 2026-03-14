# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/proxy/providers/kuaidl_proxy.py
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


# -*- coding: utf-8 -*-
# @Author  : relakkes@gmail.com
# @Time    : 2024/4/5 09:43
# @Desc    : KuaiDaili HTTP实现, 官方文档: https://www.kuaidaili.com/?ref=ldwkjqipvz6c
import os
import re
from typing import Dict, List

import httpx
from pydantic import BaseModel, Field

from proxy import IpCache, IpInfoModel, ProxyProvider
from proxy.types import ProviderNameEnum
from tools import utils

# KuaiDaili IP代理过期时间提前5秒,以避免关键时间使用失败
DELTA_EXPIRED_SECOND = 5


class KuaidailiProxyModel(BaseModel):
    ip: str = Field("ip")
    port: int = Field("port")
    expire_ts: int = Field("过期时间,单位秒,距离过期还有多少秒")


def parse_kuaidaili_proxy(proxy_info: str) -> KuaidailiProxyModel:
    """
    解析KuaiDaili IP信息
    Args:
        proxy_info:

    Returns:

    """
    proxies: List[str] = proxy_info.split(":")
    if len(proxies) != 2:
        raise Exception("无效的kuaidaili代理信息")

    pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5}),(\d+)'
    match = re.search(pattern, proxy_info)
    if not match.groups():
        raise Exception("不匹配kuaidaili代理信息")

    return KuaidailiProxyModel(
        ip=match.groups()[0],
        port=int(match.groups()[1]),
        expire_ts=int(match.groups()[2])
    )


class KuaiDaiLiProxy(ProxyProvider):
    def __init__(self, kdl_user_name: str, kdl_user_pwd: str, kdl_secret_id: str, kdl_signature: str):
        """

        Args:
            kdl_user_name:
            kdl_user_pwd:
        """
        self.kdl_user_name = kdl_user_name
        self.kdl_user_pwd = kdl_user_pwd
        self.api_base = "https://dps.kdlapi.com/"
        self.secret_id = kdl_secret_id
        self.signature = kdl_signature
        self.ip_cache = IpCache()
        self.proxy_brand_name = ProviderNameEnum.KUAI_DAILI_PROVIDER.value
        self.params = {
            "secret_id": self.secret_id,
            "signature": self.signature,
            "pt": 1,
            "format": "json",
            "sep": 1,
            "f_et": 1,
        }

    async def get_proxy(self, num: int) -> List[IpInfoModel]:
        """
        KuaiDaili实现
        Args:
            num:

        Returns:

        """
        uri = "/api/getdps/"

        # 优先从缓存获取IP
        ip_cache_list = self.ip_cache.load_all_ip(proxy_brand_name=self.proxy_brand_name)
        if len(ip_cache_list) >= num:
            return ip_cache_list[:num]

        # 如果缓存数量不足,从IP提供商获取补充,然后存入缓存
        need_get_count = num - len(ip_cache_list)
        self.params.update({"num": need_get_count})

        ip_infos: List[IpInfoModel] = []
        async with httpx.AsyncClient() as client:
            response = await client.get(self.api_base + uri, params=self.params)

            if response.status_code != 200:
                utils.logger.error(f"[KuaiDaiLiProxy.get_proxies] 状态码不是200,响应内容:{response.text}, 状态码: {response.status_code}")
                raise Exception("从代理提供商获取IP错误,状态码不是200...")

            ip_response: Dict = response.json()
            if ip_response.get("code") != 0:
                utils.logger.error(f"[KuaiDaiLiProxy.get_proxies] code不为0,消息:{ip_response.get('msg')}")
                raise Exception("从代理提供商获取IP错误,code不为0...")

            proxy_list: List[str] = ip_response.get("data", {}).get("proxy_list")
            for proxy in proxy_list:
                proxy_model = parse_kuaidaili_proxy(proxy)
                # expire_ts是相对时间(秒),需要转换为绝对时间戳
                # 提前DELTA_EXPIRED_SECOND秒考虑过期,以避免关键时间使用失败
                ip_info_model = IpInfoModel(
                    ip=proxy_model.ip,
                    port=proxy_model.port,
                    user=self.kdl_user_name,
                    password=self.kdl_user_pwd,
                    expired_time_ts=proxy_model.expire_ts + utils.get_unix_timestamp() - DELTA_EXPIRED_SECOND,

                )
                ip_key = f"{self.proxy_brand_name}_{ip_info_model.ip}_{ip_info_model.port}"
                # 缓存过期时间使用相对时间(秒),也需要减去缓冲时间
                self.ip_cache.set_ip(ip_key, ip_info_model.model_dump_json(), ex=proxy_model.expire_ts - DELTA_EXPIRED_SECOND)
                ip_infos.append(ip_info_model)

        return ip_cache_list + ip_infos


def new_kuai_daili_proxy() -> KuaiDaiLiProxy:
    """
    构造KuaiDaili HTTP实例
    支持两种环境变量命名格式:
    1. 大写格式: KDL_SECERT_ID, KDL_SIGNATURE, KDL_USER_NAME, KDL_USER_PWD
    2. 小写格式: kdl_secret_id, kdl_signature, kdl_user_name, kdl_user_pwd
    优先使用大写格式,不存在则使用小写格式
    Returns:

    """
    # 支持大写和小写环境变量格式,优先使用大写
    kdl_secret_id = os.getenv("KDL_SECERT_ID") or os.getenv("kdl_secret_id", "your_kuaidaili_secret_id")
    kdl_signature = os.getenv("KDL_SIGNATURE") or os.getenv("kdl_signature", "your_kuaidaili_signature")
    kdl_user_name = os.getenv("KDL_USER_NAME") or os.getenv("kdl_user_name", "your_kuaidaili_username")
    kdl_user_pwd = os.getenv("KDL_USER_PWD") or os.getenv("kdl_user_pwd", "your_kuaidaili_password")

    return KuaiDaiLiProxy(
        kdl_secret_id=kdl_secret_id,
        kdl_signature=kdl_signature,
        kdl_user_name=kdl_user_name,
        kdl_user_pwd=kdl_user_pwd,
    )
