import asyncio
import os
import httpx
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage

# 加载环境变量
load_dotenv()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")


# ==========================================
# 1. 核心网络层：原生 HTTP 调用百炼 MCP
# ==========================================
async def call_mcp_direct(query: str, count: int = 5) -> str:
    """直接通过 POST 请求调用百炼 MCP 的核心逻辑"""

    # 注意：百炼实际上采用的是 Streamable HTTP，直接 POST 即可
    url = "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp"

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    # 构造标准 JSON-RPC 参数
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "bailian_web_search",
            "arguments": {
                "query": query,
                "count": count
            }
        }
    }

    # 使用 httpx 发起异步 POST 请求
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=rpc_payload, headers=headers)

            if response.status_code != 200:
                return f"搜索失败，API 报错 [HTTP {response.status_code}]: {response.text}"

            data = response.json()

            # 提取搜索返回的文本结果
            try:
                return data["result"]["content"][0]["text"]
            except (KeyError, IndexError):
                return f"解析结果失败，API 原始返回内容: {data}"

        except Exception as e:
            return f"执行网络请求阶段发生异常: {str(e)}"


# ==========================================
# 2. 封装为大模型可识别的工具 (Tool)
# ==========================================
@tool
async def bailian_web_search_tool(query: str, count: int = 5) -> str:
    """
    调用百炼联网搜索 (bailian_web_search) 工具。
    可用于查询百科知识、时事新闻、天气等最新信息。

    参数:
    - query: 搜索关键词
    - count: 返回结果数量 (默认 5)
    """
    return await call_mcp_direct(query, count)


# ==========================================
# 3. 手动 Function Calling 执行流程
# ==========================================
async def main():
    if not DASHSCOPE_API_KEY:
        print("❌ 请确保已在环境变量或 .env 中设置 DASHSCOPE_API_KEY")
        return

    # 初始化大模型 (作为“大脑”)
    llm = ChatOpenAI(
        model="qwen-max",
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    # 绑定工具，告诉大模型有哪些工具可用
    llm_with_tools = llm.bind_tools([bailian_web_search_tool])

    # 初始化对话历史
    messages = [
        HumanMessage(content="请帮我查一下昨天（2026年4月26日）科技圈有什么重大新闻？")
    ]

    print("🤖 提问: " + messages[0].content)
    print("\n📤 第一轮：向大模型发起请求，大模型正在思考...")

    ai_msg = await llm_with_tools.ainvoke(messages)
    messages.append(ai_msg)

    # 判断模型是否要求调用工具
    if ai_msg.tool_calls:
        print(f"\n🛠️  大模型决定调用工具！共 {len(ai_msg.tool_calls)} 个请求。")

        for tool_call in ai_msg.tool_calls:
            print(f"   -> 正在执行: {tool_call['name']}，参数: {tool_call['args']}")

            # 执行网络搜索
            tool_result = await bailian_web_search_tool.ainvoke(tool_call["args"])

            # [可选] 打印一部分搜索结果看看
            print(f"   [DEBUG] 搜索返回预览: {str(tool_result)[:150]}...")

            # 将结果打包加入上下文
            tool_msg = ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"])
            messages.append(tool_msg)

        print("\n📥 第二轮：将搜索结果喂给大模型，生成最终总结回答...")
        final_msg = await llm_with_tools.ainvoke(messages)

        print("\n✅ 最终回答：\n")
        print(final_msg.content)

    else:
        print("\n✅ 模型认为不需要联网搜索，直接给出回答：\n")
        print(ai_msg.content)


if __name__ == "__main__":
    asyncio.run(main())