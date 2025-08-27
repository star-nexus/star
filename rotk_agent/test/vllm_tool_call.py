import json

def get_current_temperature(location: str, unit: str = "celsius"):
    """Get current temperature at a location.

    Args:
        location: The location to get the temperature for, in the format "City, State, Country".
        unit: The unit to return the temperature in. Defaults to "celsius". (choices: ["celsius", "fahrenheit"])

    Returns:
        the temperature, the location, and the unit in a dict
    """
    return {
        "temperature": 26.1,
        "location": location,
        "unit": unit,
    }


def get_temperature_date(location: str, date: str, unit: str = "celsius"):
    """Get temperature at a location and date.

    Args:
        location: The location to get the temperature for, in the format "City, State, Country".
        date: The date to get the temperature for, in the format "Year-Month-Day".
        unit: The unit to return the temperature in. Defaults to "celsius". (choices: ["celsius", "fahrenheit"])

    Returns:
        the temperature, the location, the date and the unit in a dict
    """
    return {
        "temperature": 25.9,
        "location": location,
        "date": date,
        "unit": unit,
    }


def get_function_by_name(name):
    if name == "get_current_temperature":
        return get_current_temperature
    if name == "get_temperature_date":
        return get_temperature_date

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_temperature",
            "description": "Get current temperature at a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": 'The location to get the temperature for, in the format "City, State, Country".',
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": 'The unit to return the temperature in. Defaults to "celsius".',
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_temperature_date",
            "description": "Get temperature at a location and date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": 'The location to get the temperature for, in the format "City, State, Country".',
                    },
                    "date": {
                        "type": "string",
                        "description": 'The date to get the temperature for, in the format "Year-Month-Day".',
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": 'The unit to return the temperature in. Defaults to "celsius".',
                    },
                },
                "required": ["location", "date"],
            },
        },
    },
]
MESSAGES = [
    {"role": "user",  "content": "What's the temperature in San Francisco now? How about tomorrow? Current Date: 2024-09-30."},
]

from openai import OpenAI

tools = TOOLS
messages = MESSAGES

# openai_api_key = "EMPTY"
openai_api_base = "http://172.16.75.202:10000/v1"

client = OpenAI(
    api_key = "EMPTY",
    base_url=openai_api_base,
)

model_name = "Qwen/Qwen3-32B"

response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=tools,
    temperature=0.7,
    top_p=0.8,
    max_tokens=512,
    extra_body={
        "repetition_penalty": 1.05,
        "chat_template_kwargs": {"enable_thinking": False}  # default to True
    },
)

print(response.choices[0])

messages.append(response.choices[0].message.model_dump())

if tool_calls := messages[-1].get("tool_calls", None):
    for tool_call in tool_calls:
        call_id: str = tool_call["id"]
        if fn_call := tool_call.get("function"):
            fn_name: str = fn_call["name"]
            fn_args: dict = json.loads(fn_call["arguments"])

            fn_res: str = json.dumps(get_function_by_name(fn_name)(**fn_args))

            messages.append({
                "role": "tool",
                "content": fn_res,
                "tool_call_id": call_id,
            })


response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=tools,
    temperature=0.7,
    top_p=0.8,
    max_tokens=512,
    extra_body={
        "repetition_penalty": 1.05,
        "chat_template_kwargs": {"enable_thinking": False}  # default to True
    },
)

messages.append(response.choices[0].message.model_dump())

print("====================================")
print(response.choices[0].message.content)
