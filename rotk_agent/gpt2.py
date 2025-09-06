from openai import OpenAI

client = OpenAI(base_url="http://172.16.75.203:10000/v1", api_key="EMPTY")

response = client.responses.create(
    model="/home/Assets/models/gpt-oss-20b",
    input="Use the code_exec tool to print hello world to the console.",
    tools=[
        {
            "type": "function",
            "name": "code_exec",
            "description": "Executes arbitrary Python code.",
        }
    ]
)
print(response.output)