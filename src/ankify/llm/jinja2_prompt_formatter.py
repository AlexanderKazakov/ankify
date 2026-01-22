import jinja2

from typing import Any


def jinja2_raise(message: str) -> None:
    raise jinja2.TemplateRuntimeError(message)


class PromptRenderer:
    @staticmethod
    def render(
        template_content: str,
        context: dict[str, Any],
    ) -> str:
        env = jinja2.Environment(
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=jinja2.StrictUndefined,
        )
        env.globals["fail"] = jinja2_raise
        template = env.from_string(template_content)
        return template.render(**context)
