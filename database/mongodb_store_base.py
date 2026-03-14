# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件是 MediaCrawler 项目的一部分。
# 仓库地址：https://github.com/NanmiCoder/MediaCrawler/blob/main/database/mongodb_store_base.py
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
MongoDB 存储基础类模块

提供 MongoDB 连接管理和通用存储方法
用于支持 MongoDB 作为数据存储后端
"""

import asyncio
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from config import db_config
from tools import utils


class MongoDBConnection:
    """
    MongoDB 连接管理类（单例模式）

    使用单例模式确保整个应用程序只有一个 MongoDB 连接实例
    线程安全，支持异步操作
    """
    _instance = None
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        """单例模式：确保只创建一个实例"""
        if cls._instance is None:
            cls._instance = super(MongoDBConnection, cls).__new__(cls)
        return cls._instance

    async def get_client(self) -> AsyncIOMotorClient:
        """
        获取 MongoDB 客户端

        使用双重检查锁定确保线程安全
        首次调用时建立连接

        返回:
            AsyncIOMotorClient: MongoDB 异步客户端
        """
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    await self._connect()
        return self._client

    async def get_db(self) -> AsyncIOMotorDatabase:
        """
        获取 MongoDB 数据库实例

        首次调用时建立连接

        返回:
            AsyncIOMotorDatabase: MongoDB 异步数据库实例
        """
        if self._db is None:
            async with self._lock:
                if self._db is None:
                    await self._connect()
        return self._db

    async def _connect(self):
        """
        建立 MongoDB 连接

        从配置中读取连接参数
        支持有认证和无认证两种连接方式
        连接成功后测试连接并选择数据库
        """
        try:
            # 获取 MongoDB 配置
            mongo_config = db_config.mongodb_config
            host = mongo_config["host"]
            port = mongo_config["port"]
            user = mongo_config["user"]
            password = mongo_config["password"]
            db_name = mongo_config["db_name"]

            # 构建连接 URL（支持有认证和无认证）
            if user and password:
                connection_url = f"mongodb://{user}:{password}@{host}:{port}/"
            else:
                connection_url = f"mongodb://{host}:{port}/"

            # 创建异步客户端，设置连接超时时间
            self._client = AsyncIOMotorClient(connection_url, serverSelectionTimeoutMS=5000)
            # 测试连接是否成功
            await self._client.server_info()
            # 选择数据库
            self._db = self._client[db_name]
            utils.logger.info(f"[MongoDBConnection] Connected to {host}:{port}/{db_name}")
        except Exception as e:
            utils.logger.error(f"[MongoDBConnection] Connection failed: {e}")
            raise

    async def close(self):
        """
        关闭 MongoDB 连接

        关闭客户端连接并重置实例变量
        """
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None
            utils.logger.info("[MongoDBConnection] Connection closed")


class MongoDBStoreBase:
    """
    MongoDB 存储基础类

    提供通用的 CRUD（创建、读取、更新、删除）操作方法
    每个平台使用独立的集合（collection），集合名称格式：{prefix}_{suffix}
    """

    def __init__(self, collection_prefix: str):
        """
        初始化存储基础类

        参数:
            collection_prefix: 平台前缀（如 xhs、douyin、bilibili 等）
        """
        self.collection_prefix = collection_prefix
        self._connection = MongoDBConnection()

    async def get_collection(self, collection_suffix: str) -> AsyncIOMotorCollection:
        """
        获取 MongoDB 集合

        集合名称格式：{prefix}_{suffix}
        例如：xhs_note、douyin_aweme 等

        参数:
            collection_suffix: 集合后缀（如 note、aweme、comment 等）

        返回:
            AsyncIOMotorCollection: MongoDB 异步集合
        """
        db = await self._connection.get_db()
        collection_name = f"{self.collection_prefix}_{collection_suffix}"
        return db[collection_name]

    async def save_or_update(self, collection_suffix: str, query: Dict, data: Dict) -> bool:
        """
        保存或更新数据（ upsert 操作）

        如果数据存在则更新，不存在则插入

        参数:
            collection_suffix: 集合后缀
            query: 查询条件字典，用于匹配要更新的文档
            data: 要保存或更新的数据字典

        返回:
            bool: 操作是否成功
        """
        try:
            collection = await self.get_collection(collection_suffix)
            # 使用 update_one 进行 upsert 操作
            await collection.update_one(query, {"$set": data}, upsert=True)
            return True
        except Exception as e:
            utils.logger.error(f"[MongoDBStoreBase] Save failed ({self.collection_prefix}_{collection_suffix}): {e}")
            return False

    async def find_one(self, collection_suffix: str, query: Dict) -> Optional[Dict]:
        """
        查询单条记录

        参数:
            collection_suffix: 集合后缀
            query: 查询条件字典

        返回:
            Optional[Dict]: 匹配的文档，如果不存在则返回 None
        """
        try:
            collection = await self.get_collection(collection_suffix)
            return await collection.find_one(query)
        except Exception as e:
            utils.logger.error(f"[MongoDBStoreBase] Find one failed ({self.collection_prefix}_{collection_suffix}): {e}")
            return None

    async def find_many(self, collection_suffix: str, query: Dict, limit: int = 0) -> List[Dict]:
        """
        查询多条记录

        参数:
            collection_suffix: 集合后缀
            query: 查询条件字典
            limit: 返回记录数量限制，0 表示不限制

        返回:
            List[Dict]: 匹配的文档列表
        """
        try:
            collection = await self.get_collection(collection_suffix)
            cursor = collection.find(query)
            # 如果设置了限制，则应用限制
            if limit > 0:
                cursor = cursor.limit(limit)
            return await cursor.to_list(length=None)
        except Exception as e:
            utils.logger.error(f"[MongoDBStoreBase] Find many failed ({self.collection_prefix}_{collection_suffix}): {e}")
            return []

    async def create_index(self, collection_suffix: str, keys: List[tuple], unique: bool = False):
        """
        创建索引

        参数:
            collection_suffix: 集合后缀
            keys: 索引键列表，格式：[("field", 1)]，1 表示升序，-1 表示降序
            unique: 是否为唯一索引
        """
        try:
            collection = await self.get_collection(collection_suffix)
            await collection.create_index(keys, unique=unique)
            utils.logger.info(f"[MongoDBStoreBase] Index created on {self.collection_prefix}_{collection_suffix}")
        except Exception as e:
            utils.logger.error(f"[MongoDBStoreBase] Create index failed: {e}")
