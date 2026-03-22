# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawlerPro-Python project.
# Repository: https://github.com/MediaCrawlerPro/MediaCrawlerPro-Python/blob/main/repo/checkpoint/__init__.py
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

from config import CHECKPOINT_STORAGE_TYPE
from .checkpoint_store import (
    CheckpointJsonFileRepo,
    CheckpointRedisRepo,
    CheckpointRepoManager,
)


def create_checkpoint_manager(
    storage_type: str = CHECKPOINT_STORAGE_TYPE, **kwargs
) -> CheckpointRepoManager:
    """创建检查点管理器的工厂函数

    Args:
        storage_type (str): 存储类型，支持 "file" 或 "redis"
        **kwargs: 额外的参数传递给对应的存储库构造函数

    Returns:
        CheckpointRepoManager: 检查点管理器实例
    """
    if storage_type.lower() == "redis":
        repo = CheckpointRedisRepo(**kwargs)
    elif storage_type.lower() == "file":
        repo = CheckpointJsonFileRepo(**kwargs)
    else:
        raise ValueError(f"不支持的存储类型: {storage_type}")

    return CheckpointRepoManager(repo)
