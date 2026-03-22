# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/websocket.py
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

import asyncio
from typing import Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import crawler_manager

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """向所有连接广播消息"""
        if not self.active_connections:
            return

        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


async def log_broadcaster():
    """后台任务：从队列读取日志并广播"""
    queue = crawler_manager.get_log_queue()
    while True:
        try:
            # 从队列获取日志条目
            entry = await queue.get()
            # 广播到所有WebSocket连接
            await manager.broadcast(entry.model_dump())
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"日志广播错误：{e}")
            await asyncio.sleep(0.1)


# 全局广播任务
_broadcaster_task: Optional[asyncio.Task] = None


def start_broadcaster():
    """启动广播任务"""
    global _broadcaster_task
    if _broadcaster_task is None or _broadcaster_task.done():
        _broadcaster_task = asyncio.create_task(log_broadcaster())


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket日志流"""
    print("[WS] 新的连接尝试")

    try:
        # 确保广播任务正在运行
        start_broadcaster()

        await manager.connect(websocket)
        print(f"[WS] 已连接，活动连接数：{len(manager.active_connections)}")

        # 发送现有日志
        for log in crawler_manager.logs:
            try:
                await websocket.send_json(log.model_dump())
            except Exception as e:
                print(f"[WS] 发送现有日志错误：{e}")
                break

        print(f"[WS] 已发送{len(crawler_manager.logs)}条现有日志，进入主循环")

        while True:
            # 保持连接活跃，接收心跳或任何消息
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 发送ping以保持连接
                try:
                    await websocket.send_text("ping")
                except Exception as e:
                    print(f"[WS] 发送ping错误：{e}")
                    break

    except WebSocketDisconnect:
        print("[WS] 客户端断开连接")
    except Exception as e:
        print(f"[WS] 错误：{type(e).__name__}：{e}")
    finally:
        manager.disconnect(websocket)
        print(f"[WS] 清理完成，活动连接数：{len(manager.active_connections)}")


@router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """WebSocket状态流"""
    await websocket.accept()

    try:
        while True:
            # 每秒发送状态
            status = crawler_manager.get_status()
            await websocket.send_json(status)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
