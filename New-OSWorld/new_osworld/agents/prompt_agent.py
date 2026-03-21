"""Main prompt-based agent that drives LLM calls for desktop automation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from new_osworld.agents.base import BaseAgent
from new_osworld.agents.llm_clients import create_llm_client
from new_osworld.agents.prompts import get_system_prompt
from new_osworld.agents.utils.a11y_tree import linearize_accessibility_tree, trim_accessibility_tree
from new_osworld.agents.utils.image_utils import encode_image_bytes
from new_osworld.agents.utils.parsing import (
    parse_actions_from_string,
    parse_code_from_som_string,
    parse_code_from_string,
)
from new_osworld.logging_setup import get_logger

_default_logger = get_logger("agent")


class PromptAgent(BaseAgent):
    """Agent that builds multi-turn prompts and calls an LLM for action prediction.

    Supports multiple observation types (screenshot, a11y tree, both, SOM) and
    action spaces (pyautogui code, structured actions).

    Args:
        platform: ``"ubuntu"`` or ``"windows"``.
        model: Model identifier passed to the LLM client factory.
        max_tokens: Max generation tokens.
        top_p: Nucleus sampling threshold.
        temperature: Sampling temperature.
        action_space: ``"pyautogui"`` or ``"computer_13"``.
        observation_type: ``"screenshot"``, ``"a11y_tree"``,
            ``"screenshot_a11y_tree"``, or ``"som"``.
        max_trajectory_length: How many past turns to include in the prompt.
        a11y_tree_max_tokens: Token budget for the linearised a11y tree.
        client_password: VM sudo password (injected into prompts).
    """

    def __init__(
        self,
        platform: str = "ubuntu",
        model: str = "gpt-4o",
        max_tokens: int = 1500,
        top_p: float = 0.9,
        temperature: float = 0.5,
        action_space: str = "pyautogui",
        observation_type: str = "screenshot_a11y_tree",
        max_trajectory_length: int = 3,
        a11y_tree_max_tokens: int = 10000,
        client_password: str = "password",
    ) -> None:
        super().__init__(action_space=action_space)
        self.platform = platform
        self.model = model
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.temperature = temperature
        self.observation_type = observation_type
        self.max_trajectory_length = max_trajectory_length
        self.a11y_tree_max_tokens = a11y_tree_max_tokens
        self.client_password = client_password

        self.llm = create_llm_client(model)
        self.system_message = get_system_prompt(observation_type, action_space, client_password)

        self._thoughts: List[str] = []
        self._actions: List[Any] = []
        self._observations: List[Dict[str, Any]] = []

    def reset(self, runtime_logger: Optional[logging.Logger] = None) -> None:
        """Clear episode state."""
        super().reset(runtime_logger)
        self._thoughts.clear()
        self._actions.clear()
        self._observations.clear()

    def predict(
        self,
        instruction: str,
        obs: Dict[str, Any],
    ) -> Tuple[str, Optional[List[Any]]]:
        """Build a prompt from the trajectory, call the LLM, and parse actions.

        Args:
            instruction: The task instruction.
            obs: Current observation dict.

        Returns:
            ``(response_text, actions)`` -- *actions* is *None* on parse failure.
        """
        messages = self._build_messages(instruction, obs)

        try:
            response = self.llm.chat(
                messages,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                temperature=self.temperature,
            )
        except Exception as exc:
            self._logger.error("LLM call failed for %s: %s", self.model, exc)
            response = ""

        self._logger.info("LLM response: %s", response[:500])

        try:
            actions = self._parse_response(response)
            self._thoughts.append(response)
        except ValueError as exc:
            self._logger.warning("Action parse failed: %s", exc)
            actions = None
            self._thoughts.append("")

        return response, actions

    # ------------------------------------------------------------------
    # Message construction
    # ------------------------------------------------------------------

    def _build_messages(self, instruction: str, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Assemble the multi-turn message list for the LLM."""
        sys_text = self.system_message + f"\nYou are asked to complete the following task: {instruction}"
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": [{"type": "text", "text": sys_text}]}
        ]

        hist_obs, hist_act, hist_tht = self._get_history_window()
        for prev_obs, prev_action, prev_thought in zip(hist_obs, hist_act, hist_tht):
            messages.append(self._obs_to_user_msg(prev_obs))
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": prev_thought.strip() or "No valid action"}],
            })

        current_obs_record = self._process_current_obs(obs)
        self._observations.append(current_obs_record)
        messages.append(self._obs_to_user_msg(current_obs_record, obs=obs))

        return messages

    def _get_history_window(self):
        """Return the most recent N turns of trajectory."""
        n = self.max_trajectory_length
        if n == 0 or not self._observations:
            return [], [], []
        return self._observations[-n:], self._actions[-n:], self._thoughts[-n:]

    def _process_current_obs(self, obs: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Encode / linearise the current observation and return a record."""
        record: Dict[str, Optional[str]] = {"screenshot": None, "accessibility_tree": None}

        if self.observation_type in ("screenshot", "screenshot_a11y_tree"):
            screenshot = obs.get("screenshot")
            record["screenshot"] = encode_image_bytes(screenshot) if screenshot else None

        if self.observation_type in ("a11y_tree", "screenshot_a11y_tree"):
            raw_tree = obs.get("accessibility_tree")
            if raw_tree:
                lin = linearize_accessibility_tree(raw_tree, self.platform)
                lin = trim_accessibility_tree(lin, self.a11y_tree_max_tokens)
                record["accessibility_tree"] = lin

        if self.observation_type == "som":
            # SOM tagging (requires external filter_nodes / draw_bounding_boxes)
            screenshot = obs.get("screenshot")
            record["screenshot"] = encode_image_bytes(screenshot) if screenshot else None

        return record

    def _obs_to_user_msg(
        self,
        record: Dict[str, Optional[str]],
        obs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convert an observation record into an LLM user message."""
        content: List[Dict[str, Any]] = []

        if self.observation_type == "screenshot_a11y_tree":
            tree = record.get("accessibility_tree", "")
            content.append({
                "type": "text",
                "text": f"Given the screenshot and accessibility tree:\n{tree}\nWhat's the next step?",
            })
            if record.get("screenshot"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{record['screenshot']}", "detail": "high"},
                })
        elif self.observation_type == "screenshot":
            content.append({"type": "text", "text": "Given the screenshot. What's the next step?"})
            if record.get("screenshot"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{record['screenshot']}", "detail": "high"},
                })
        elif self.observation_type == "a11y_tree":
            tree = record.get("accessibility_tree", "")
            content.append({
                "type": "text",
                "text": f"Given the accessibility tree:\n{tree}\nWhat's the next step?",
            })
        elif self.observation_type == "som":
            content.append({"type": "text", "text": "Given the tagged screenshot. What's the next step?"})
            if record.get("screenshot"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{record['screenshot']}", "detail": "high"},
                })

        return {"role": "user", "content": content}

    # ------------------------------------------------------------------
    # Action parsing
    # ------------------------------------------------------------------

    def _parse_response(self, response: str) -> List[Any]:
        """Dispatch to the appropriate parser based on observation/action mode."""
        if self.observation_type in ("screenshot", "a11y_tree", "screenshot_a11y_tree"):
            if self.action_space == "computer_13":
                actions = parse_actions_from_string(response)
            else:
                actions = parse_code_from_string(response)
        elif self.observation_type == "som":
            actions = parse_code_from_string(response)
        else:
            raise ValueError(f"Unknown observation type: {self.observation_type}")

        self._actions.append(actions)
        return actions
