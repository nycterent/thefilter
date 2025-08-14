"""Voice system for newsletter commentary generation."""

from .base import VoiceGenerator, VoiceConfig
from .saint import SAINT_PROMPT_TEMPLATE, SAINT_CONFIG

# Voice registry
AVAILABLE_VOICES = {
    "saint": {
        "template": SAINT_PROMPT_TEMPLATE,
        "config": SAINT_CONFIG
    }
}

def get_voice(voice_name: str) -> dict:
    """Get voice template and configuration.
    
    Args:
        voice_name: Name of the voice to retrieve
        
    Returns:
        Dictionary with 'template' and 'config' keys
        
    Raises:
        ValueError: If voice_name is not found
    """
    if voice_name not in AVAILABLE_VOICES:
        available = ", ".join(AVAILABLE_VOICES.keys())
        raise ValueError(f"Voice '{voice_name}' not found. Available: {available}")
    
    return AVAILABLE_VOICES[voice_name]

def list_voices() -> list:
    """List all available voice names."""
    return list(AVAILABLE_VOICES.keys())