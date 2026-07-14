"""
Name Generator step (brief section 3), scoped down from 5-20k names to a
fast, cheap ~150-250 batch for the MVP.

Judgment call: rather than hand-rolling a word-blending / markov generator,
this reuses the same Claude integration as the Brand Strategist step with a
second, single, structured-output call. It's simpler than building and
tuning a rule-based generator, produces noticeably better invented/compound
names, and is still one cheap API call -- well within "fast and cheap" for
an MVP. The brief only specifies Claude (not GPT-5.5) for the Brand
Strategist step; nothing prohibits using it here too, and this workspace has
no non-Claude LLM access anyway.
"""
import json
import os

import anthropic

MODEL_ID = os.environ.get("NAMEZY_CLAUDE_MODEL", "claude-opus-4-8")
DEFAULT_TARGET_COUNT = int(os.environ.get("NAMEZY_CANDIDATE_COUNT", "200"))

NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "names": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "method": {
                        "type": "string",
                        "enum": ["invented", "compound", "theme"],
                    },
                },
                "required": ["name", "method"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["names"],
    "additionalProperties": False,
}

SYSTEM_PROMPT_TEMPLATE = (
    "You are a brand name generator. Given a brand profile (personality "
    "traits, words to avoid, seed keywords), generate {count} candidate "
    "brand/product names. Use a mix of three methods: 'invented' (novel "
    "coined words, phonetically pleasant), 'compound' (two real or seed "
    "words fused or joined), and 'theme' (a seed keyword lightly altered -- "
    "spelling change, suffix, shortening). Rules: each name 3-16 characters, "
    "no spaces, no punctuation besides an optional single internal hyphen, "
    "no numbers unless part of deliberate wordplay, nothing from the avoid "
    "list, no existing real trademarked brand names, no duplicates within "
    "your output. Favor names that are easy to say and spell aloud. Return "
    "as close to {count} names as you reasonably can."
)


class NameGeneratorError(RuntimeError):
    """Raised when the Name Generator step cannot produce usable candidates."""


def generate_candidates(brand_profile: dict, target_count: int = DEFAULT_TARGET_COUNT) -> list[dict]:
    """Returns a list of {"name": str, "method": "invented"|"compound"|"theme"}."""
    client = anthropic.Anthropic()
    no_credentials_msg = (
        "Could not authenticate with Claude. Set the ANTHROPIC_API_KEY "
        "environment variable in your .env file."
    )

    user_content = (
        f"Personality traits: {', '.join(brand_profile.get('personality_traits', []))}\n"
        f"Avoid: {', '.join(brand_profile.get('avoid_words', []))}\n"
        f"Seed keywords: {', '.join(brand_profile.get('seed_keywords', []))}\n"
        f"Generate {target_count} candidate names now."
    )

    try:
        # thinking must be disabled: with it on, thinking tokens are drawn from the
        # same max_tokens budget as the JSON output and can consume all of it,
        # leaving no room for the actual response.
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=8192,
            system=SYSTEM_PROMPT_TEMPLATE.format(count=target_count),
            thinking={"type": "disabled"},
            output_config={"format": {"type": "json_schema", "schema": NAME_SCHEMA}},
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AuthenticationError as exc:
        raise NameGeneratorError(no_credentials_msg) from exc
    except TypeError as exc:
        # The SDK raises a plain TypeError (not AuthenticationError) when it
        # can't resolve ANY credential source at all.
        raise NameGeneratorError(no_credentials_msg) from exc
    except anthropic.APIError as exc:
        raise NameGeneratorError(f"Claude API error during name generation: {exc}") from exc

    text = next((block.text for block in response.content if block.type == "text"), None)
    if not text:
        raise NameGeneratorError("Claude returned no usable output for name generation.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NameGeneratorError("Claude's name-generation response was not valid JSON.") from exc

    names = data.get("names", [])
    if not names:
        raise NameGeneratorError("Claude returned zero candidate names.")
    return names
