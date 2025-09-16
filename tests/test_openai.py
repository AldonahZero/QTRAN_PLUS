import os
import openai

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("环境变量 OPENAI_API_KEY 未设置")
else:
    client = openai.OpenAI(api_key=api_key)
    try:
        models = client.models.list()
        print("API 访问成功，模型列表：")
        for m in models.data:
            print(m.id)
    except Exception as e:
        print("API 访问失败，错误信息：")
        print(e)