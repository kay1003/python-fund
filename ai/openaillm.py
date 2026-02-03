from openai import OpenAI


client = OpenAI(
  api_key="xxxxxx",
)

response = client.responses.create(
  model="gpt-5-nano",
  input="你是大模型吗谁家公司的，另外你如何看待中国的ai应用开发发展",
  store=True,
)

print(response.output_text);