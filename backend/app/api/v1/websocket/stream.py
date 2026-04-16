
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from starlette.websockets import WebSocketState
from app.service.agent_service import AgentService

# 假设你已经建好了这个 Service
# from app.services.agent_service import KyberonGraphService

router = APIRouter()

# 全局实例化一个 Service（实际项目中可以配合 FastAPI 的生命周期或 Depends 注入）
agent_service = AgentService()


# 模拟依赖注入
def get_graph_service():
    # 实际项目中，这里应该返回配置好 SQLite checkpointer 的 LangGraph 实例
    pass


@router.websocket("/{session_id}")
async def agent_ws_stream(
        websocket: WebSocket,
        session_id: str,
        # service: KyberonGraphService = Depends(get_graph_service) # 实际开发时取消注释
):
    """
    处理与前端的 WebSocket 实时通信
    """
    # 1. 接受前端连接
    await websocket.accept()
    print(f"[WebSocket] Session {session_id} connected.")

    try:
        # 2. 保持长连接，等待用户输入
        while True:
            # 接收前端发来的 JSON 数据
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
                continue

            user_message = data.get("message")
            if not user_message:
                continue

            # 3. 告诉前端：后端已经收到消息，Agent 开始运行了
            await websocket.send_json({
                "type": "status",
                "content": "Agent thinking..."
            })

            # 4. 调用 Service 层的 LangGraph 逻辑，并实时将结果推给前端
            async for chunk in agent_service.run_graph(session_id, user_message):
                # 如果连接已断开，停止发送
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    break
                await websocket.send_json(chunk)

            # 4. 调用 Service 层的 LangGraph 逻辑，并实时将结果推给前端
            # 注意：这里的 service.run_graph 是一个异步生成器 (async yield)
            """
            async for chunk in service.run_graph(session_id, user_message):
                # chunk 可能是 {"type": "log", "content": "Planner Node is running"}
                # 也可能是 {"type": "assistant", "content": "您需要移动端吗？"}
                # 也可能是 {"type": "interrupt", "content": "wait_for_user"}

                # 如果连接已断开，停止发送
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    break

                await websocket.send_json(chunk)
            """

            # (开发阶段的 Mock 逻辑：当你还没写好 Service 时，先用这个测试前后端联调)
            # import asyncio
            # await asyncio.sleep(1)
            # await websocket.send_json({"type": "log", "node": "planner", "content": "正在分析您的需求..."})
            # await asyncio.sleep(1.5)
            # await websocket.send_json({"type": "assistant", "content": "听起来是个好主意！请问需要支持多语言吗？"})
            # await websocket.send_json({"type": "interrupt", "content": "wait_for_user"})

    except WebSocketDisconnect:
        print(f"[WebSocket] Session {session_id} disconnected normally.")
    except Exception as e:
        print(f"[WebSocket] Error in session {session_id}: {str(e)}")
        # 尝试优雅地通知前端发生错误
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json({"type": "error", "content": "Internal Server Error"})