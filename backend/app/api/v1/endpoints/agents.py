# backend/app/api/v1/endpoints/agents.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# 定义请求数据的结构（Schema）
class AgentTask(BaseModel):
    instruction: str
    session_id: str

router = APIRouter()

@router.post("/run")
async def run_code_agent(task: AgentTask):
    """
    接收用户指令，启动 Master Agent 调度任务
    """
    # 这里以后会调用 Service 层逻辑，比如：
    # task_id = await master_service.dispatch(task.instruction)
    return {"status": "success", "message": f"Task received for {task.session_id}"}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态
    """
    return {"task_id": task_id, "status": "processing"}