# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/kuaishou/graphql.py
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


# Kuaishou's data transmission is based on GraphQL
# This class is responsible for obtaining some GraphQL schemas
"""
快手 GraphQL 查询模块

负责加载和管理快手 API 的 GraphQL 查询语句
快手的数据传输基于 GraphQL 协议
"""

from typing import Dict


class KuaiShouGraphQL:
    """
    快手 GraphQL 查询类
    
    负责从本地文件加载 GraphQL 查询语句
    """
    graphql_queries: Dict[str, str]= {}

    def __init__(self):
        """
        初始化 GraphQL 查询加载器
        
        设置 GraphQL 文件目录并加载查询语句
        """
        self.graphql_dir = "media_platform/kuaishou/graphql/"
        self.load_graphql_queries()

    def load_graphql_queries(self):
        """
        加载 GraphQL 查询文件
        
        从 graphql 目录读取所有 .graphql 文件并存储到字典中
        """
        graphql_files = ["search_query.graphql", "video_detail.graphql", "comment_list.graphql", "vision_profile.graphql","vision_profile_photo_list.graphql","vision_profile_user_list.graphql","vision_sub_comment_list.graphql"]

        for file in graphql_files:
            with open(self.graphql_dir + file, mode="r") as f:
                query_name = file.split(".")[0]
                self.graphql_queries[query_name] = f.read()

    def get(self, query_name: str) -> str:
        """
        获取指定名称的 GraphQL 查询
        
        参数:
            query_name: 查询名称（不含 .graphql 后缀）
            
        返回:
            GraphQL 查询语句字符串
            
        抛出:
            如果查询不存在返回错误信息
        """
        return self.graphql_queries.get(query_name, "Query not found")
