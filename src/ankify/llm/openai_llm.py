import openai

from .llm_base import LLMClient
from ..settings import LLMConfig, OpenAIProviderAccess


class OpenAIClient(LLMClient):
    """Any OpenAI-compatible API"""
    def __init__(self, llm_config: LLMConfig, openai_access: OpenAIProviderAccess) -> None:
        super().__init__(llm_config.options.model)
        api_key = openai_access.api_key.get_secret_value()
        self._reasoning_effort = llm_config.options.reasoning_effort
        self._client = openai.OpenAI(api_key=api_key, base_url=openai_access.base_url)
        endpoint = openai_access.base_url or "[OpenAI-default-endpoint]"
        self._logger.info("Initialized OpenAI client, model '%s', endpoint '%s', reasoning_effort '%s'", 
                          self._model, endpoint, self._reasoning_effort)

    # we don't need retry here, it's handled within the openai sdk
    def _call_llm(self, instructions: str, input_text: str) -> tuple[str, dict]:
        self._logger.info("Calling OpenAI API for model '%s', this may take a while...", self._model)
        
        kwargs = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
        }
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort

        # using old-style API, because not all providers support the new responses API
        response = self._client.chat.completions.create(**kwargs)
        self._logger.info("OpenAI API call completed")

        return response.choices[0].message.content, response.usage
