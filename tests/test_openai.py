import os
import openai
import sys

# 说明：此脚本会读取环境变量 OPENAI_API_KEY 并可选通过 HTTP(S) 代理（Clash 默认 127.0.0.1:7890）访问 OpenAI。
# 用法示例：
#   # 不走代理
#   OPENAI_API_KEY=sk-... python tests/test_openai.py
#   # 走 Clash HTTP 代理
#   OPENAI_API_KEY=sk-... HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890 python tests/test_openai.py

api_key = os.getenv("OPENAI_API_KEY")
http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

print(f"OPENAI_API_KEY set: {bool(api_key)}")
print(f"HTTP_PROXY: {http_proxy}")
print(f"HTTPS_PROXY: {https_proxy}")

if not api_key:
    print("环境变量 OPENAI_API_KEY 未设置，跳过 API 调用")
    sys.exit(0)

# 配置 openai 客户端（新版 openai 库）
client = openai.OpenAI(api_key=api_key)

try:
    models = client.models.list()
    print("API 访问成功，模型列表：")
    for m in models.data:
        print(m.id)
except Exception as e:
    print("API 访问失败，错误信息：")
    print(e)
