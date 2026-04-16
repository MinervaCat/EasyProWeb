# backend/app/main.py
from fastapi import FastAPI
from app.api.router import root_router

app = FastAPI(title="KyberonCode API")

# 将总路由挂载到 app 实例
app.include_router(root_router)

@app.get("/")
async def root():
    return {"message": "Welcome to KyberonCode API"}