from pydantic import BaseModel


class Soul(BaseModel):
    name: str = "Agent"
    organization: str = "OpenAI"  # Anthropic , OpenAI, Bedrock_Anthropic
    model: str = "gpt-4o"  # gpt-4o , claude-3-5-sonnet-20241022
