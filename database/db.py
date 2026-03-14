# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/database/db.py
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
数据库初始化模块

提供数据库表结构初始化和关闭连接的统一接口
"""

import asyncio
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path，以便正确导入模块
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tools import utils
from database.db_session import create_tables


async def init_table_schema(db_type: str):
    """
    初始化数据库表结构

    根据 ORM 模型创建数据库表

    参数:
        db_type: 数据库类型，可选值为 'sqlite'、'mysql' 或 'postgres'

    说明:
        此函数会调用 create_tables 函数来创建所有定义的数据库表
    """
    utils.logger.info(f"[init_table_schema] begin init {db_type} table schema ...")
    # 调用 db_session 模块中的 create_tables 函数创建表
    await create_tables(db_type)
    utils.logger.info(f"[init_table_schema] {db_type} table schema init successful")


async def init_db(db_type: str = None):
    """
    初始化数据库

    便捷函数，封装了表结构初始化操作

    参数:
        db_type: 数据库类型，可选值为 'sqlite'、'mysql' 或 'postgres'
    """
    await init_table_schema(db_type)


async def close():
    """
    关闭数据库连接

    占位函数，为未来需要关闭数据库连接时预留
    目前各数据库引擎由 SQLAlchemy 自行管理连接池
    """
    pass
