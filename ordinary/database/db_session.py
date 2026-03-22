# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/database/db_session.py
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
数据库会话管理模块

提供数据库引擎创建、表结构初始化和会话管理功能
支持 SQLite、MySQL、PostgreSQL 等多种数据库
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
from .models import Base
import config
from config.db_config import mysql_db_config, sqlite_db_config, postgres_db_config

# 引擎缓存字典，用于缓存已创建的数据库引擎，避免重复创建
_engines = {}


async def create_database_if_not_exists(db_type: str):
    """
    如果数据库不存在，则创建数据库

    参数:
        db_type: 数据库类型，可选值为 'mysql'、'postgres'

    说明:
        对于 MySQL，连接到服务器后创建指定的数据库
        对于 PostgreSQL，连接到默认数据库后创建指定的数据库
    """
    # MySQL 数据库处理
    if db_type == "mysql" or db_type == "db":
        # 连接到 MySQL 服务器（不指定数据库）
        server_url = f"mysql+asyncmy://{mysql_db_config['user']}:{mysql_db_config['password']}@{mysql_db_config['host']}:{mysql_db_config['port']}"
        engine = create_async_engine(server_url, echo=False)
        async with engine.connect() as conn:
            # 创建数据库（如果不存在）
            await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {mysql_db_config['db_name']}"))
        # 关闭引擎连接
        await engine.dispose()

    # PostgreSQL 数据库处理
    elif db_type == "postgres":
        # 连接到 PostgreSQL 默认数据库
        server_url = f"postgresql+asyncpg://{postgres_db_config['user']}:{postgres_db_config['password']}@{postgres_db_config['host']}:{postgres_db_config['port']}/postgres"
        print(f"[init_db] Connecting to Postgres: host={postgres_db_config['host']}, port={postgres_db_config['port']}, user={postgres_db_config['user']}, dbname=postgres")
        # 需要 AUTOCOMMIT 隔离级别才能执行 CREATE DATABASE
        engine = create_async_engine(server_url, echo=False, isolation_level="AUTOCOMMIT")
        async with engine.connect() as conn:
            # 检查数据库是否已存在
            result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{postgres_db_config['db_name']}'"))
            if not result.scalar():
                # 创建数据库
                await conn.execute(text(f"CREATE DATABASE {postgres_db_config['db_name']}"))
        # 关闭引擎连接
        await engine.dispose()


def get_async_engine(db_type: str = None):
    """
    获取异步数据库引擎

    参数:
        db_type: 数据库类型，可选值为 'sqlite'、'mysql'、'postgres'、'json'、'jsonl'、'csv'
                如果为 None，则使用 config.SAVE_DATA_OPTION 配置

    返回:
        异步数据库引擎对象

    说明:
        支持缓存机制，相同的数据库类型会返回同一个引擎实例
        JSON/JSONL/CSV 类型返回 None，表示使用文件存储
    """
    # 如果未指定数据库类型，使用全局配置
    if db_type is None:
        db_type = config.SAVE_DATA_OPTION

    # 如果引擎已存在，直接返回缓存的引擎
    if db_type in _engines:
        return _engines[db_type]

    # JSON/JSONL/CSV 使用文件存储，不需要数据库引擎
    if db_type in ["json", "jsonl", "csv"]:
        return None

    # 根据数据库类型构建连接 URL
    if db_type == "sqlite":
        db_url = f"sqlite+aiosqlite:///{sqlite_db_config['db_path']}"
    elif db_type == "mysql" or db_type == "db":
        db_url = f"mysql+asyncmy://{mysql_db_config['user']}:{mysql_db_config['password']}@{mysql_db_config['host']}:{mysql_db_config['port']}/{mysql_db_config['db_name']}"
    elif db_type == "postgres":
        db_url = f"postgresql+asyncpg://{postgres_db_config['user']}:{postgres_db_config['password']}@{postgres_db_config['host']}:{postgres_db_config['port']}/{postgres_db_config['db_name']}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    # 创建异步引擎
    engine = create_async_engine(db_url, echo=False)
    # 缓存引擎
    _engines[db_type] = engine
    return engine


async def create_tables(db_type: str = None):
    """
    创建数据库表

    参数:
        db_type: 数据库类型，可选值为 'sqlite'、'mysql'、'postgres'

    说明:
        根据 models.py 中定义的 ORM 模型创建所有数据库表
        对于 MySQL 和 PostgreSQL，会先创建数据库（如果不存在）
    """
    # 如果未指定数据库类型，使用全局配置
    if db_type is None:
        db_type = config.SAVE_DATA_OPTION

    # 先创建数据库（如果不存在）
    await create_database_if_not_exists(db_type)

    # 获取数据库引擎
    engine = get_async_engine(db_type)

    # 如果引擎存在，创建所有表
    if engine:
        async with engine.begin() as conn:
            # 使用 ORM 模型创建所有表
            await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """
    获取数据库会话的上下文管理器

    用途:
        在 with 语句中使用，自动管理会话的提交和回滚

    示例:
        async with get_session() as session:
            session.add(some_object)
            # 自动提交

    说明:
        会自动处理异常，如果发生异常会自动回滚
        无论是否发生异常，最后都会关闭会话
    """
    # 获取数据库引擎
    engine = get_async_engine(config.SAVE_DATA_OPTION)

    # 如果引擎不存在（使用文件存储），返回 None
    if not engine:
        yield None
        return

    # 创建异步会话工厂
    AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # 创建会话
    session = AsyncSessionFactory()

    try:
        # 交付会话给调用者
        yield session
        # 正常结束时提交事务
        await session.commit()
    except Exception as e:
        # 发生异常时回滚事务
        await session.rollback()
        # 重新抛出异常
        raise e
    finally:
        # 无论成功或失败，最后都关闭会话
        await session.close()
