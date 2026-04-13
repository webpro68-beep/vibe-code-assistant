from __future__ import annotations

from typing import Iterable, List

from app.models import StrategyDirective
from app.state import AppState


class DirectiveDispatcher:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def dispatch(self, directives: Iterable[StrategyDirective]) -> List[StrategyDirective]:
        directives = list(directives)
        self.state.directives.extend(directives)
        return directives
