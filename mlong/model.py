"""
Adapted from https://github.com/andrewyng/aisuite/blob/main/aisuite/client.py
"""

from typing import List
from mlong.provider import ProviderFactory
from mlong.types.type_chat import ChatResponse


class Model:
    def __init__(self, model_configs: dict = None):
        """
        模型的一个抽象, 通过 model 可以调用不同的模型, 但是 model 本身并不关心模型的实现细节, 只关心模型的调用方式.
        """
        # self.default_model = "aws.us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        self.default_model = "aws.us.amazon.nova-pro-v1:0"
        # Configs
        if model_configs is None:
            self.model_configs = {}
        else:
            self.model_configs = model_configs

        # Backends
        self.backends = {}

        # API
        self._chat = None
        self._embed = None

        # Init
        self.init_backends()

    def init_backends(self):
        for provider, config in self.model_configs.items():
            provider = self.validate(provider)
            self.backends[provider] = ProviderFactory.provider(provider, config)

    def validate(self, provider):
        available_provider = ProviderFactory.list_provider()
        if provider not in available_provider:
            raise ValueError(f"Provider {provider} is not supported")
        return provider

    def chat(self, model: str = None, messages: List[str] = [], **kwargs):
        if model is None:
            model = self.default_model
        if "." not in model:
            raise ValueError("Model must be in the format of 'provider.model'")

        provider, model = model.split(".", 1)

        available_provider = ProviderFactory.list_provider()

        if provider not in available_provider:
            raise ValueError(f"Provider {provider} is not supported")

        if provider not in self.backends:
            config = self.model_configs.get(provider, {})
            self.backends[provider] = ProviderFactory.provider(provider, config)

        model_client = self.backends.get(provider)

        if not model_client:
            raise ValueError(f"Provider {provider} is not supported")

        return model_client.chat(messages=messages, model=model, **kwargs)

    # @property
    # def embed(self):
    #     if not self._embed:
    #         self._embed = Embed(self)
    #     return self._embed
