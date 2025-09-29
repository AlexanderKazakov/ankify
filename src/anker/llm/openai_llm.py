import openai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .llm_base import LLMClient
from ..settings import LLMConfig


class OpenAIClient(LLMClient):
    def __init__(self, llm_config: LLMConfig) -> None:
        super().__init__()
        self._api_key = llm_config.providers.openai.api_key.get_secret_value()
        self._model = llm_config.options.model
        self._client = openai.OpenAI(api_key=self._api_key)
        self._logger.debug("Initialized OpenAI client")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type(openai.OpenAIError),
    )
    def _call_llm(self, instructions: str, input_text: str) -> str:
        self._logger.info("Calling OpenAI API for model '%s', this may take a while...", self._model)
        answer = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=input_text,
            store=False,
        )
        self._logger.info("OpenAI API call completed")
        return answer.output_text
