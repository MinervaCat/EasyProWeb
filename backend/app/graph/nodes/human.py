from app.graph.state.state import AgentState
from langchain_core.runnables import RunnableConfig

class HumanNode:
    async def run(self, state: AgentState, config: RunnableConfig):
        if state["status"] == "plan_completed":
            last_msg = state["messages"][-1]
            print(last_msg)