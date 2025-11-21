import openai

from .llm_base import LLMClient
from ..settings import LLMConfig, OpenAIProviderAccess


class OpenAIClient(LLMClient):
    def __init__(self, llm_config: LLMConfig, openai_access: OpenAIProviderAccess) -> None:
        super().__init__()
        api_key = openai_access.api_key.get_secret_value()
        self._model = llm_config.options.model
        self._client = openai.OpenAI(api_key=api_key)
        self._logger.debug("Initialized OpenAI client")

    # we don't need retry here, it's handled within the openai sdk
    def _call_llm(self, instructions: str, input_text: str) -> tuple[str, dict]:
        self._logger.info("Calling OpenAI API for model '%s', this may take a while...", self._model)
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=input_text,
            store=False,
        )
        self._logger.info("OpenAI API call completed")

        usage = {
            "model": self._model,
            "usage": response.usage.to_dict(),
        }
        return response.output_text, usage
