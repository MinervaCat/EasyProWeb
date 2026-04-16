# backend/app/api/router.py
from fastapi import APIRouter
from app.api.v1.api import api_v1_router

root_router = APIRouter()

# 所有的 v1 接口都会带上 /api/v1 前缀
root_router.include_router(api_v1_router, prefix="/api/v1")