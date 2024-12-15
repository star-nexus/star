import pydantic
import json
import toml


from .lltypes import *
from ..utils import *
from .llm import *


class Agent:

    def __init__(
        self,
        key_config_path,
        model_config_path: str = "cyber/configs/default_model.toml",
        agent_config_path: str = "cyber/configs/default_agent.toml",
    ):
        self.key_config = toml.load(key_config_path)
        self.agent_config = toml.load(agent_config_path)
        self.model_config = toml.load(model_config_path)
        self.soul = Soul(**self.agent_config["Soul"])
        self.client = self.get_client_base_model(self.soul)

    def chat(
        self,
        prompt="",
        system="",
        history_context=[],
        model=None,
        tools=None,
        tool_choice=None,
        stream=False,
    ):
        """
        Chat with the agent and get response.
        """
        history = history_context
        messages = history + [build_user_message(prompt)]

        params = {
            "model": model or self.soul.model,
            "messages": messages,
            "tools": tools or None,
            "tool_choice": tool_choice or None,
            "stream": stream,
            "system": system,
        }
        response = self.send_messages(**params)
        history = history + [build_assistant_message(response)]
        return response, history

    def send_messages(self, **p):
        params = {}
        match self.soul.organization:
            case "OpenAI":
                if p.messages:
                    params.update({"messages": p.messages})
                if p.system != "":
                    params.update(
                        {
                            "messages": [build_system_message(p["system"])]
                            + p["messages"]
                        }
                    )
                if p.tools:
                    params.update({"tools": p.tools})
                if p.tool_choice:
                    params.update({"tool_choice": p.tool_choice})
                if p.stream:
                    params.update({"stream": p.stream})
                if p.model:
                    params.update({"model": p.model})

                # print(params)

                res = self.client.chat.completions.create(**params)
                calculate_price(res.model, res.usage)
            case "Anthropic":
                params.update({"system": p["system"]})
                params.update({"max_tokens": 8192})
                print(params)
                res = self.client.messages.create(**params)
                calculate_price(res.model, res.usage)
            case "Bedrock_Anthropic":  # pass test
                if p["messages"]:
                    params.update({"messages": p["messages"]})
                if p["system"]:
                    params.update({"system": p["system"]})
                params.update({"max_tokens": 1000})
                params.update({"temperature": 0.1})
                params.update({"anthropic_version": "bedrock-2023-05-31"})
                model = p["model"]

                # print(params)
                res = interact_with_bedrock_anthropic(
                    self.client, model, params, stream=False
                )
            case "Custom":
                pass
        return res

    def run_with_stream():
        pass

    def run(self, prompts, stream):
        if stream:
            return self.run_with_stream()
        self.chat(prompts, stream=stream)

    def get_client_base_model(self, soul):
        match soul.organization:
            case "OpenAI":
                from openai import OpenAI

                client = OpenAI(
                    organization=self.key_config["openai"]["organization"],
                    project=self.key_config["openai"]["project"],
                    api_key=self.key_config["openai"]["api_key"],
                )
                return client
            case "Anthropic":
                from anthropic import Anthropic

                client = Anthropic(api_key=self.key_config["anthropic"]["api_key"])
                return client
            case "Bedrock_Anthropic":
                import boto3
                from botocore.config import Config

                proxy_url = self.key_config["proxy"]["url"]
                proxy_config = Config(proxies={"http": proxy_url, "https": proxy_url})
                client = boto3.client(
                    service_name=self.key_config["bedrock"]["service_name"],
                    config=proxy_config,
                    region_name=self.key_config["bedrock"]["region_name"],
                    aws_access_key_id=self.key_config["bedrock"]["aws_access_key_id"],
                    aws_secret_access_key=self.key_config["bedrock"][
                        "aws_secret_access_key"
                    ],
                )
                return client
