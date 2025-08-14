"""Voice management system for newsletter commentary generation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .voices import get_voice, list_voices, AVAILABLE_VOICES
from .voices.base import VoiceGenerator, VoiceConfig, SaintVoiceGenerator

logger = logging.getLogger(__name__)


class VoiceManager:
    """Manages voice templates and generation for newsletter commentary."""
    
    def __init__(self, default_voice: str = "saint"):
        self.default_voice = default_voice
        self._generators = {}
        self._load_voices()
    
    def _load_voices(self):
        """Load all available voice generators."""
        for voice_name in list_voices():
            try:
                voice_data = get_voice(voice_name)
                config = VoiceConfig(**voice_data["config"])
                
                # Create appropriate generator based on voice type
                if voice_name == "saint":
                    generator = SaintVoiceGenerator(voice_data["template"], config)
                else:
                    # Default generator for other voices
                    generator = VoiceGenerator(voice_data["template"], config)
                
                self._generators[voice_name] = generator
                logger.debug(f"Loaded voice: {voice_name}")
                
            except Exception as e:
                logger.error(f"Failed to load voice '{voice_name}': {e}")
    
    def get_voice_generator(self, voice_name: Optional[str] = None) -> VoiceGenerator:
        """Get voice generator by name.
        
        Args:
            voice_name: Name of voice to get, or None for default
            
        Returns:
            VoiceGenerator instance
            
        Raises:
            ValueError: If voice not found
        """
        voice_name = voice_name or self.default_voice
        
        if voice_name not in self._generators:
            available = ", ".join(self._generators.keys())
            raise ValueError(f"Voice '{voice_name}' not available. Available: {available}")
        
        return self._generators[voice_name]
    
    def generate_commentary(
        self,
        content: str,
        notes: str = "",
        voice: Optional[str] = None,
        language: str = "en",
        target_words: int = 700,
        image_subject: Optional[str] = None,
        llm_client=None
    ) -> Dict[str, Any]:
        """Generate voice commentary for content.
        
        Args:
            content: Content highlights/summary to analyze
            notes: Additional notes or context
            voice: Voice to use (None for default)
            language: Target language
            target_words: Target word count
            image_subject: Subject for image prompt
            llm_client: LLM client to use for generation
            
        Returns:
            Dictionary with generated commentary and metadata
            
        Raises:
            ValueError: If generation fails
        """
        try:
            generator = self.get_voice_generator(voice)
            
            # Generate prompt
            prompt = generator.generate_prompt(
                highlights=content,
                notes=notes,
                language=language,
                target_words=target_words,
                image_subject=image_subject
            )
            
            logger.debug(f"Generated prompt for voice '{voice or self.default_voice}'")
            
            if not llm_client:
                raise ValueError("LLM client is required for commentary generation")
            
            # Generate response using LLM
            response = llm_client.generate_text(prompt)
            
            # Parse and format response
            parsed_response = generator.parse_response(response)
            formatted_response = generator.format_for_newsletter(parsed_response)
            
            # Add metadata
            formatted_response["voice_metadata"] = {
                "voice": voice or self.default_voice,
                "language": language,
                "target_words": target_words,
                "prompt_length": len(prompt),
                "response_length": len(response)
            }
            
            logger.info(f"Generated commentary using voice '{voice or self.default_voice}'")
            return formatted_response
            
        except Exception as e:
            logger.error(f"Failed to generate commentary: {e}")
            raise
    
    def generate_multi_language(
        self,
        content: str,
        notes: str = "",
        voice: Optional[str] = None,
        languages: List[str] = ["en", "lt"],
        target_words: int = 700,
        image_subject: Optional[str] = None,
        llm_client=None
    ) -> Dict[str, Dict[str, Any]]:
        """Generate commentary in multiple languages.
        
        Args:
            content: Content to analyze
            notes: Additional notes
            voice: Voice to use
            languages: List of languages to generate
            target_words: Target word count per language
            image_subject: Subject for image prompt
            llm_client: LLM client
            
        Returns:
            Dictionary mapping language codes to commentary data
        """
        results = {}
        generator = self.get_voice_generator(voice)
        
        # Filter languages to only those supported by the voice
        supported_languages = generator.config.languages
        valid_languages = [lang for lang in languages if lang in supported_languages]
        
        if not valid_languages:
            logger.warning(f"No valid languages found. Supported by voice: {supported_languages}")
            valid_languages = [supported_languages[0]]  # Use first supported language
        
        for language in valid_languages:
            try:
                result = self.generate_commentary(
                    content=content,
                    notes=notes,
                    voice=voice,
                    language=language,
                    target_words=target_words,
                    image_subject=image_subject,
                    llm_client=llm_client
                )
                results[language] = result
                logger.info(f"Generated commentary for language: {language}")
                
            except Exception as e:
                logger.error(f"Failed to generate commentary for language '{language}': {e}")
                # Continue with other languages
        
        return results
    
    def list_available_voices(self) -> List[Dict[str, Any]]:
        """List all available voices with their configurations.
        
        Returns:
            List of voice information dictionaries
        """
        voices = []
        for name, generator in self._generators.items():
            voices.append({
                "name": name,
                "description": generator.config.description,
                "languages": generator.config.languages,
                "themes": generator.config.themes,
                "default_options": generator.config.default_options
            })
        return voices
    
    def add_custom_voice(self, voice_file_path: str):
        """Add a custom voice from a Python file.
        
        Args:
            voice_file_path: Path to Python file with voice definition
            
        The file should contain:
        - VOICE_PROMPT_TEMPLATE: The prompt template string
        - VOICE_CONFIG: Configuration dictionary
        """
        try:
            # Import the custom voice file
            import importlib.util
            spec = importlib.util.spec_from_file_location("custom_voice", voice_file_path)
            custom_voice = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(custom_voice)
            
            # Extract voice data
            template = getattr(custom_voice, "VOICE_PROMPT_TEMPLATE")
            config_dict = getattr(custom_voice, "VOICE_CONFIG")
            
            # Create voice generator
            config = VoiceConfig(**config_dict)
            generator = SaintVoiceGenerator(template, config)  # Use Saint as default
            
            # Register voice
            voice_name = config.name.lower()
            self._generators[voice_name] = generator
            
            logger.info(f"Added custom voice: {voice_name}")
            
        except Exception as e:
            logger.error(f"Failed to add custom voice from {voice_file_path}: {e}")
            raise