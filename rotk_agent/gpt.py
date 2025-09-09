from openai import OpenAI
import json
from rich.console import Console
console = Console()

client = OpenAI(base_url="http://172.16.75.203:10000/v1", api_key="EMPTY")

# 1. Define a list of callable tools for the model
tools = [
    {
        "type": "function",
        "name": "perform_action",
        "description": "Get today's horoscope for an astrological sign.",
        "parameters": {
            "type": "object",
            "properties": {
                "sign": {
                    "type": "string",
                    "description": "An astrological sign like Taurus or Aquarius",
                },
            },
            "required": ["sign"],
        },
    },
]

def perform_action(sign):
    # return f"{sign}: Next Tuesday you will befriend a baby otter."
    return json.dumps({"success": True, "state": "active", "faction": "wei", "total_units": 5, "alive_units": 5, 
"actionable_units": 5, "units": [{"unit_id": 231, "unit_type": "infantry", "faction": "wei", "position": {"col": 3,
"row": 3}, "status": {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", 
"fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 1, "vision_range": 2, "action_points": 2, 
"max_action_points": 2, "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, 
{"unit_id": 232, "unit_type": "archer", "faction": "wei", "position": {"col": 4, "row": 3}, "status": 
{"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, 
"capabilities": {"movement": 10, "attack_range": 3, "vision_range": 4, "action_points": 2, "max_action_points": 2, 
"attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, {"unit_id": 233, "unit_type": 
"archer", "faction": "wei", "position": {"col": 4, "row": 2}, "status": {"current_count": 100, "max_count": 100, 
"health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 3,
"vision_range": 4, "action_points": 2, "max_action_points": 2, "attack_points": 1, "construction_points": 1, 
"skill_points": 1}, "available_skills": []}, {"unit_id": 234, "unit_type": "archer", "faction": "wei", "position": 
{"col": 3, "row": 2}, "status": {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": 
"normal", "fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 3, "vision_range": 4, "action_points":
2, "max_action_points": 2, "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, 
{"unit_id": 235, "unit_type": "cavalry", "faction": "wei", "position": {"col": 2, "row": 3}, "status": 
{"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, 
"capabilities": {"movement": 15, "attack_range": 1, "vision_range": 3, "action_points": 2, "max_action_points": 2, 
"attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}]})
    
    # """
#     {"success": true, "state": "active", "faction": "wei", "total_units": 5, "alive_units": 5, 
# "actionable_units": 5, "units": [{"unit_id": 231, "unit_type": "infantry", "faction": "wei", "position": {"col": 3,
# "row": 3}, "status": {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", 
# "fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 1, "vision_range": 2, "action_points": 2, 
# "max_action_points": 2, "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, 
# {"unit_id": 232, "unit_type": "archer", "faction": "wei", "position": {"col": 4, "row": 3}, "status": 
# {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, 
# "capabilities": {"movement": 10, "attack_range": 3, "vision_range": 4, "action_points": 2, "max_action_points": 2, 
# "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, {"unit_id": 233, "unit_type": 
# "archer", "faction": "wei", "position": {"col": 4, "row": 2}, "status": {"current_count": 100, "max_count": 100, 
# "health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 3,
# "vision_range": 4, "action_points": 2, "max_action_points": 2, "attack_points": 1, "construction_points": 1, 
# "skill_points": 1}, "available_skills": []}, {"unit_id": 234, "unit_type": "archer", "faction": "wei", "position": 
# {"col": 3, "row": 2}, "status": {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": 
# "normal", "fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 3, "vision_range": 4, "action_points":
# 2, "max_action_points": 2, "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, 
# {"unit_id": 235, "unit_type": "cavalry", "faction": "wei", "position": {"col": 2, "row": 3}, "status": 
# {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, 
# "capabilities": {"movement": 15, "attack_range": 1, "vision_range": 3, "action_points": 2, "max_action_points": 2, 
# "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}]}
# """

# Create a running input list we will add to over time
input_list = [
    {"role": "user", "content": "What is my horoscope? I am an Aquarius."}
]

# 2. Prompt the model with tools defined
response = client.responses.create(
    model="/home/Assets/models/gpt-oss-20b",
    tools=tools,
    input=input_list,
    stream=False,
)

print("First output:")
print(response.model_dump_json(indent=2))

# Save function call outputs for subsequent requests
input_list += response.output

console.print("Input list:")
console.print(input_list)

for item in response.output:
    if item.type == "function_call":
        if item.name == "perform_action":
            # 3. Execute the function logic for get_horoscope
            horoscope = perform_action(json.loads(item.arguments))
            
            # 4. Provide function call results to the model
            input_list.append({
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": json.dumps({
                  "horoscope": horoscope
                })
            })

print("Final input:")
console.print(input_list)

response = client.responses.create(
    model="/home/Assets/models/gpt-oss-20b",
    instructions="Respond only with a horoscope generated by a tool.",
    tools=tools,
    input=input_list,
)

# 5. The model should be able to give a response!
print("Final output:")
print(response.model_dump_json(indent=2))
print("\n" + response.output_text)