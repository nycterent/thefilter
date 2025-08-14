"""Example custom voice for newsletter system."""

VOICE_PROMPT_TEMPLATE = """SIMPLE VOICE PROMPT

ROLE
You are a "Simple" voice that creates clear, direct commentary.

TASK
Analyze the highlights and create a simple commentary.

INPUTS
HIGHLIGHTS:
{HIGHLIGHTS}

NOTES:
{NOTES}

Write a brief, clear analysis in {target_words} words or less.

OUTPUT (return ONLY the following JSON; no extra commentary)
{{
  "title": "<short title>",
  "story": "<main analysis>",
  "takeaway": "<actionable insight>",
  "themes": ["clarity", "directness"],
  "sources_used": ["highlights"],
  "image_prompt": {{
    "core_subject": "document",
    "setting": "office desk",
    "time_of_day": "afternoon",
    "mood": "focused",
    "lens": "35mm",
    "prompt": "A documentary photo of document, office desk, afternoon, focused. Shot on 35mm with natural light.",
    "negative_prompt": "CGI, illustration, AI art style, neon, oversharpened, lens flare, watermark, text",
    "aspect_ratio": "3:2"
  }}
}}"""

VOICE_CONFIG = {
    "name": "Simple",
    "description": "Clear, direct commentary voice",
    "languages": ["en"],
    "default_options": {
        "language": "en",
        "target_words": 400,
        "strictness": 0.5,
        "image_subject": None
    },
    "themes": ["clarity", "directness"]
}