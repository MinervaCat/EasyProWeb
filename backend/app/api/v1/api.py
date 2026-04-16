# backend/app/api/v1/api.py
from fastapi import APIRouter
from app.api.v1.endpoints import agents
from app.api.v1.websocket import stream

api_v1_router = APIRouter()

# 挂载各个模块，并指定前缀和标签
api_v1_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
# api_v1_router.include_router(workspace.router, prefix="/workspace", tags=["Workspace"])

# 挂载 WebSocket
api_v1_router.include_router(stream.router, prefix="/ws", tags=["Realtime"])