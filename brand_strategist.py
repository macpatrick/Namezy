"""
Brand Strategist step (brief section 2).

Calls Claude once, with a JSON-schema-constrained response, to turn a free-text
company/product description into a structured brand profile: personality
traits, words/themes to avoid, and seed keywords for the Name Generator step.

Uses the official `anthropic` Python SDK (not the `claude` CLI, and not raw
HTTP) -- it's the documented, supported path and needs no extra process
management. Requires the ANTHROPIC_API_KEY environment variable to be set;
the SDK has no other way to resolve credentials.
"""
import json
import os

import anthropic

MODEL_ID = os.environ.get("NAMEZY_CLAUDE_MODEL", "claude-opus-4-8")

BRAND_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "personality_traits": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-6 adjectives describing the brand personality",
        },
        "avoid_words": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Words, themes, or connotations the name should avoid",
        },
        "seed_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "8-15 seed words / word-fragments / themes for a name "
                "generator to draw from"
            ),
        },
    },
    "required": ["personality_traits", "avoid_words", "seed_keywords"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are a brand strategist. Given a short description of a company or "
    "product, extract a structured brand profile: the personality traits it "
    "should convey, words/themes/connotations it should avoid, and seed "
    "keywords a name generator can draw from (a mix of literal words, "
    "evocative/thematic words, and a few word fragments, prefixes, or "
    "suffixes with a relevant sound or meaning). Be concise and specific to "
    "the input -- do not return generic branding boilerplate."
)


class BrandStrategistError(RuntimeError):
    """Raised when the Brand Strategist step cannot produce a usable profile."""


def extract_brand_profile(description: str) -> dict:
    """Returns {"personality_traits": [...], "avoid_words": [...], "seed_keywords": [...]}"""
    if not description or not description.strip():
        raise BrandStrategistError("Description is empty.")

    no_credentials_msg = (
        "Could not authenticate with Claude. Set the ANTHROPIC_API_KEY "
        "environment variable in your .env file."
    )

    client = anthropic.Anthropic()

    try:
        # thinking must be disabled: with it on, thinking tokens are drawn from the
        # same max_tokens budget as the JSON output and can consume all of it,
        # leaving no room for the actual response.
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            thinking={"type": "disabled"},
            output_config={
                "format": {"type": "json_schema", "schema": BRAND_PROFILE_SCHEMA}
            },
            messages=[{"role": "user", "content": description.strip()}],
        )
    except anthropic.AuthenticationError as exc:
        raise BrandStrategistError(no_credentials_msg) from exc
    except TypeError as exc:
        # The SDK raises a plain TypeError (not AuthenticationError) when it
        # can't resolve ANY credential source at all -- no ANTHROPIC_API_KEY,
        # no ANTHROPIC_AUTH_TOKEN.
        raise BrandStrategistError(no_credentials_msg) from exc
    except anthropic.APIError as exc:
        raise BrandStrategistError(f"Claude API error: {exc}") from exc

    text = next((block.text for block in response.content if block.type == "text"), None)
    if not text:
        raise BrandStrategistError("Claude returned no usable output.")

    try:
        profile = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BrandStrategistError("Claude's response was not valid JSON.") from exc

    return profile
