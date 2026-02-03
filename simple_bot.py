import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# 初始化一个全局的 ChatOpenAI 实例，避免每次调用都重新连接
llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME"),
    openai_api_base=os.getenv("OPENAI_API_BASE"),
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

def get_bot_response(user_input: str) -> str:
    """
    核心函数：接收用户文本 -> 调用大模型 -> 返回回复
    """
    try:
        response = llm.invoke(user_input)
        return response.content
    except Exception as e:
        return f"Sorry, AI brain error: {str(e)}"

def test_bot():
    print("🤖 Sending request to:", llm.model_name)
    print("✅ Response:", get_bot_response("Hello!"))

if __name__ == "__main__":
    test_bot()
