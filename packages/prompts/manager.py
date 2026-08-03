from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PromptTemplate:
    name: str
    template: str
    version: int = 1


@dataclass(slots=True)
class PromptVersion:
    id: str
    template: PromptTemplate
    content: str


@dataclass(slots=True)
class PromptStore:
    templates: dict[str, PromptTemplate] = field(default_factory=dict)
    versions: list[PromptVersion] = field(default_factory=list)

    def add_template(self, template: PromptTemplate) -> None:
        self.templates[template.name] = template

    def render(self, name: str, **variables: Any) -> str:
        template = self.templates[name]
        rendered = template.template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered
