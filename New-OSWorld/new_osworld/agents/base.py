"""Abstract base class for all desktop-automation agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from new_osworld.logging_setup import get_logger

_default_logger = get_logger("agent")


class BaseAgent(ABC):
    """Every agent must implement :meth:`predict` and :meth:`reset`.

    Subclasses may carry trajectory state (observations, thoughts, actions)
    between calls to :meth:`predict`.  A call to :meth:`reset` clears that
    state so the agent can be reused across episodes.
    """

    def __init__(self, action_space: str = "pyautogui") -> None:
        self.action_space = action_space
        self._logger: logging.Logger = _default_logger

    @abstractmethod
    def predict(
        self,
        instruction: str,
        obs: Dict[str, Any],
    ) -> Tuple[str, Optional[List[Any]]]:
        """Decide the next action(s) given an observation.

        Args:
            instruction: The natural-language task description.
            obs: Observation dict with keys ``screenshot``, ``accessibility_tree``,
                ``terminal``, ``instruction``.

        Returns:
            A ``(raw_response, actions)`` tuple where *actions* is a list of
            action strings / dicts (or *None* on parse failure).
        """

    def reset(self, runtime_logger: Optional[logging.Logger] = None) -> None:
        """Clear trajectory state and optionally attach a per-episode logger.

        Args:
            runtime_logger: If provided, replaces the agent's internal logger
                for the duration of the next episode.
        """
        self._logger = runtime_logger or _default_logger
