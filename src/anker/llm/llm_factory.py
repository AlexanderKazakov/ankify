from ..settings import Settings
from .llm_base import LLMClient
from .openai_llm import OpenAIClient
from ..logging import get_logger


def create_llm_client(settings: Settings) -> LLMClient:
    logger = get_logger("anker.llm.factory")
    llm_config = settings.llm
    provider = llm_config.provider
    if provider == "openai":
        logger.debug("Creating LLM client for provider '%s' and model '%s'", provider, llm_config.options.model)
        openai_access = settings.providers.openai
        return OpenAIClient(llm_config=llm_config, openai_access=openai_access)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


