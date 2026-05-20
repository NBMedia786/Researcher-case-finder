from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass
class IngestedArticle:
    url: str
    title: str | None
    published_at: datetime | None
    raw_text: str
    source_name: str
    source_type: str


class BaseSource:
    name: str = ""
    source_type: str = ""

    def __init__(self, config: dict):
        self.config = config

    def fetch(self) -> Iterable[IngestedArticle]:
        raise NotImplementedError
