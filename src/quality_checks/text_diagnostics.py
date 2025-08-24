import re
from typing import List, Dict, Tuple
import nltk
from nltk.corpus import stopwords
from textstat import flesch_reading_ease, flesch_kincaid_grade


class TextDiagnostics:
    """Advanced text analysis for journalistic content."""

    def __init__(self, text: str):
        self.text = text
        nltk.download("stopwords", quiet=True)
        self.stop_words = set(stopwords.words("english"))

    def readability_analysis(self) -> Dict[str, float]:
        """Compute readability metrics."""
        return {
            "flesch_reading_ease": flesch_reading_ease(self.text),
            "flesch_kincaid_grade": flesch_kincaid_grade(self.text),
        }

    def passive_voice_detection(self) -> List[Tuple[str, int]]:
        """Detect passive voice constructions."""
        passive_patterns = [
            r"\b(is|was|were|be|been)\b.*\b(by)\b",  # Classic passive voice
            r"\b(being)\b.*\b(by)\b",  # Gerund passive voice
        ]

        passive_instances = []
        for line_num, line in enumerate(self.text.split("\n"), 1):
            for pattern in passive_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    passive_instances.append((line, line_num))

        return passive_instances

    def jargon_analysis(self, custom_jargon_list: List[str] = None) -> List[str]:
        """Detect industry-specific jargon and corporate buzzwords."""
        default_jargon = [
            "synergy",
            "leverage",
            "ecosystem",
            "disruptive",
            "mission-critical",
            "scalable",
            "innovative",
        ]

        jargon_list = (custom_jargon_list or []) + default_jargon
        detected_jargon = [
            word for word in jargon_list if word.lower() in self.text.lower()
        ]

        return detected_jargon

    def semantic_density_score(self) -> float:
        """Calculate the semantic density of the text."""
        words = [
            word.lower()
            for word in re.findall(r"\w+", self.text)
            if word.lower() not in self.stop_words
        ]

        unique_words = len(set(words))
        total_words = len(words)

        return unique_words / total_words if total_words > 0 else 0


def comprehensive_text_analysis(text: str, custom_jargon: List[str] = None) -> Dict:
    """Perform comprehensive text diagnostics."""
    diagnostics = TextDiagnostics(text)

    return {
        "readability": diagnostics.readability_analysis(),
        "passive_voice_instances": diagnostics.passive_voice_detection(),
        "detected_jargon": diagnostics.jargon_analysis(custom_jargon),
        "semantic_density": diagnostics.semantic_density_score(),
    }
