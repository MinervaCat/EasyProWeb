import os
import docker
import asyncio
from pathlib import Path


class SandboxManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SandboxManager, cls).__new__(cls)
            # 只有第一次初始化时执行
            cls._instance.client = docker.from_env()
            cls._instance.image_name = "easypro-sandbox"
            # 使用绝对路径：确保无论在哪里启动，都能找到项目的 workspaces
            cls._instance.base_workspace = Path(__file__).parent.parent.parent / "workspaces"
        return cls._instance

    # 既然在 __new__ 里初始化了，__init__ 就可以省去，防止重复赋值

    async def run_test(self, session_id: str, command: str, timeout: int = 15):
        # 1. 路径处理
        host_path = self.base_workspace / session_id
        # 确保宿主机目录已存在（如果是新 session）
        if not host_path.exists():
            host_path.mkdir(parents=True, exist_ok=True)

        container_path = "/workspace"
        container_name = f"sandbox-{session_id}"

        try:
            # 2. 异步获取或创建容器
            def get_or_create_container():
                try:
                    container = self.client.containers.get(container_name)
                    if container.status != "running":
                        container.start()
                    return container
                except docker.errors.NotFound:
                    return self.client.containers.run(
                        self.image_name,
                        name=container_name,
                        detach=True,
                        # 核心魔法：挂载
                        volumes={str(host_path.absolute()): {'bind': container_path, 'mode': 'rw'}},
                        tty=True,
                        # 限制资源（可选，防止 Agent 耗尽服务器内存）
                        mem_limit="512m"
                    )

            # 将同步的 Docker SDK 调用放入线程池执行，防止阻塞主事件循环
            container = await asyncio.to_thread(get_or_create_container)

            # 3. 在容器内执行命令
            # 建议加上 timeout 保护
            full_command = f"timeout {timeout}s bash -c '{command}'"

            def execute():
                # 使用 demux=True 可以清晰分离出 stdout 和 stderr
                return container.exec_run(full_command, workdir=container_path, demux=True)

            exit_code, output = await asyncio.to_thread(execute)
            stdout, stderr = output

            # 4. 解码处理
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

            if exit_code == 0:
                return f"✅ SUCCESS:\n{stdout_str}"
            elif exit_code == 124:
                return f"❌ TIMEOUT: Command exceeded {timeout}s"
            else:
                return f"❌ FAILED (Exit {exit_code}):\n{stderr_str or stdout_str}"

        except Exception as e:
            return f"❌ 沙盒系统错误: {str(e)}"