"""YAML-based voice configuration system - replaces contaminated template injection."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CleanVoiceConfig:
    """Clean voice configuration without template contamination."""

    name: str
    description: str
    languages: List[str]
    principles: Dict[str, str]
    forbidden_phrases: List[str]
    validation_rules: List[str]
    examples: List[Dict[str, str]]
    default_options: Dict[str, Any]

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "CleanVoiceConfig":
        """Load voice configuration from YAML file."""
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            return cls(
                name=data["name"],
                description=data["description"],
                languages=data["languages"],
                principles=data["principles"],
                forbidden_phrases=data["forbidden_phrases"],
                validation_rules=data["validation_rules"],
                examples=data["examples"],
                default_options=data["default_options"],
            )
        except Exception as e:
            logger.error(f"Failed to load voice config from {yaml_path}: {e}")
            raise

    def validate_content(self, content: str) -> tuple[bool, Optional[str]]:
        """Validate content against forbidden phrases and rules.

        Returns:
            (is_valid, error_message)
        """
        content_lower = content.lower()

        # Check for forbidden phrases
        for phrase in self.forbidden_phrases:
            if phrase.lower() in content_lower:
                return False, f"Contains forbidden phrase: '{phrase}'"

        # Check for first person usage
        first_person_indicators = [" i ", " we ", " my ", " our ", " us "]
        for indicator in first_person_indicators:
            if indicator in content_lower:
                return False, "Uses first person instead of third person"

        return True, None


class CleanVoiceManager:
    """Manages clean voice configurations without template contamination."""

    def __init__(self, voices_dir: str = None):
        self.voices_dir = (
            Path(voices_dir) if voices_dir else Path(__file__).parent / "voices"
        )
        self.voices: Dict[str, CleanVoiceConfig] = {}
        self._load_voices()

    def _load_voices(self):
        """Load all YAML voice configurations."""
        if not self.voices_dir.exists():
            logger.warning(f"Voices directory does not exist: {self.voices_dir}")
            return

        for yaml_file in self.voices_dir.glob("*.yaml"):
            try:
                voice_config = CleanVoiceConfig.from_yaml(str(yaml_file))
                self.voices[voice_config.name] = voice_config
                logger.info(f"Loaded clean voice: {voice_config.name}")
            except Exception as e:
                logger.error(f"Failed to load voice from {yaml_file}: {e}")

    def get_voice(self, name: str) -> Optional[CleanVoiceConfig]:
        """Get voice configuration by name."""
        return self.voices.get(name)

    def list_voices(self) -> List[str]:
        """List available voice names."""
        return list(self.voices.keys())

    def validate_commentary(
        self, commentary: str, voice_name: str
    ) -> tuple[bool, Optional[str]]:
        """Validate commentary against voice rules."""
        voice = self.get_voice(voice_name)
        if not voice:
            return True, None  # Skip validation if voice not found

        return voice.validate_content(commentary)


# Global instance for easy access
clean_voice_manager = CleanVoiceManager()
