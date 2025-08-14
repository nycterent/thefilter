"""Base classes for voice system."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """Configuration for a voice template."""

    name: str
    description: str
    languages: List[str]
    default_options: Dict[str, Any]
    themes: List[str]


class VoiceGenerator:
    """Base class for voice generators."""

    def __init__(self, template: str, config: VoiceConfig):
        self.template = template
        self.config = config

    def generate_prompt(
        self,
        highlights: str,
        notes: str = "",
        language: str = "en",
        target_words: int = 700,
        strictness: float = 0.7,
        image_subject: Optional[str] = None,
    ) -> str:
        """Generate a formatted prompt for the voice.

        Args:
            highlights: Content highlights to analyze
            notes: Additional notes or context
            language: Target language (en, lt, etc.)
            target_words: Target word count for output
            strictness: How strictly to follow voice guidelines (0.0-1.0)
            image_subject: Optional subject for image prompt

        Returns:
            Formatted prompt string
        """
        # Validate language
        if language not in self.config.languages:
            logger.warning(
                f"Language '{language}' not supported by {self.config.name}. "
                f"Supported: {', '.join(self.config.languages)}. Using default."
            )
            language = self.config.languages[0]

        # Format image_subject for JSON
        image_subject_json = f'"{image_subject}"' if image_subject else "null"

        return self.template.format(
            HIGHLIGHTS=highlights,
            NOTES=notes,
            language=language,
            target_words=target_words,
            strictness=strictness,
            image_subject=image_subject_json,
        )

    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured format.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed response as dictionary

        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        try:
            # Try to extract JSON from response
            # Look for JSON block between { and }
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON block found in response")

            json_str = response[start_idx:end_idx]
            parsed = json.loads(json_str)

            # Validate required fields
            required_fields = ["title", "story", "takeaway"]
            missing_fields = [field for field in required_fields if field not in parsed]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            raise ValueError(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"Error parsing voice response: {e}")
            raise

    def format_for_newsletter(self, parsed_response: Dict[str, Any]) -> Dict[str, Any]:
        """Format parsed response for newsletter inclusion.

        Args:
            parsed_response: Parsed LLM response

        Returns:
            Dictionary formatted for newsletter template
        """
        # Default implementation
        return {
            "title": parsed_response.get("title", "Untitled"),
            "content": parsed_response.get("story", ""),
            "takeaway": parsed_response.get("takeaway", ""),
            "voice_metadata": {"voice": "default", "language": "auto-detected"},
        }


class SaintVoiceGenerator(VoiceGenerator):
    """Saint voice generator implementation."""

    def format_for_newsletter(self, parsed_response: Dict[str, Any]) -> Dict[str, Any]:
        """Format Saint voice response for newsletter."""
        return {
            "title": parsed_response.get("title", "Untitled"),
            "content": parsed_response.get("story", ""),
            "takeaway": parsed_response.get("takeaway", ""),
            "thesis": parsed_response.get("thesis", ""),
            "angle": parsed_response.get("angle", {}),
            "themes": parsed_response.get("themes", []),
            "sources_used": parsed_response.get("sources_used", []),
            "image_prompt": parsed_response.get("image_prompt", {}),
            "voice_metadata": {
                "voice": "saint",
                "language": "auto-detected",
                "generated_at": "timestamp",
            },
        }
