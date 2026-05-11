import logging
import os
from pathlib import Path
from typing import Optional
import asyncio

import yaml
from google import genai
from app.utils.lang_pair import normalize_lang_pair
from google.genai import types

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config" / "transcreation"

DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"


class TranscreationService:
    def __init__(self, config_dir: Path = _CONFIG_DIR):
        self._profiles: dict[str, dict] = {}
        self._client: Optional[genai.Client] = None
        self._load_profiles(config_dir)
        self._init_client()

    def _init_client(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — gemini_transcreation engine will be unavailable.")
            return
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version='v1beta'),
        )
        logger.info("TranscreationService: Gemini client initialised.")

    def _load_profiles(self, config_dir: Path):
        if not config_dir.exists():
            logger.warning(f"Transcreation config directory not found: {config_dir}")
            return
        for yaml_file in config_dir.glob("*.yaml"):
            pair = normalize_lang_pair(yaml_file.stem)
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    profile = yaml.safe_load(f)
                self._profiles[pair] = profile
                records = len(profile.get("golden_records") or [])
                logger.info(f"TranscreationService: loaded profile '{pair}' ({records} golden records).")
            except Exception as e:
                logger.error(f"TranscreationService: failed to load {yaml_file.name}: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._client is not None

    def has_profile(self, source_lang: str, target_lang: str) -> bool:
        pair = normalize_lang_pair(f"{source_lang}-{target_lang}")
        return pair in self._profiles

    def supported_pairs(self) -> list[str]:
        return list(self._profiles.keys())

    async def transcreate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Transcreate using the static YAML profile for this language pair."""
        if not self._client:
            raise RuntimeError("Gemini client not initialised — check GEMINI_API_KEY.")

        pair = normalize_lang_pair(f"{source_lang}-{target_lang}")
        profile = self._profiles.get(pair)
        if not profile:
            raise ValueError(f"No transcreation profile for pair '{pair}'.")

        system_prompt = profile.get("system_prompt", "").strip()
        golden_records = profile.get("golden_records") or []
        model = profile.get("model", DEFAULT_MODEL)

        contents: list[types.Content] = []
        for record in golden_records:
            src = record.get("source", "").strip()
            tgt = record.get("target", "").strip()
            if src and tgt:
                contents.append(types.Content(role="user", parts=[types.Part(text=src)]))
                contents.append(types.Content(role="model", parts=[types.Part(text=tgt)]))

        contents.append(types.Content(role="user", parts=[types.Part(text=text.strip())]))

        logger.info(f"TranscreationService: calling {model} for '{pair}' ({len(golden_records)} golden records)")
        await asyncio.sleep(4)
        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            ),
        )
        result = response.text.strip()
        logger.info(f"TranscreationService: received {len(result)} chars for '{pair}'.")
        return result

    async def transcreate_with_style_guide(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        style_guide,
    ) -> str:
        """Transcreate using a StyleGuide ORM object as the constraint source.

        Retrieves relevant required/forbidden terms and rules from the guide,
        injects them as a structured system prompt, and uses the YAML golden
        records for the pair (if they exist) as few-shot examples.
        """
        if not self._client:
            raise RuntimeError("Gemini client not initialised — check GEMINI_API_KEY.")

        pair = normalize_lang_pair(f"{source_lang}-{target_lang}")
        yaml_profile = self._profiles.get(pair)
        model = (yaml_profile or {}).get("model", DEFAULT_MODEL)
        golden_records = (yaml_profile or {}).get("golden_records") or []

        system_prompt = self._build_style_guide_prompt(style_guide, source_lang, target_lang)

        contents: list[types.Content] = []
        for record in golden_records:
            src = record.get("source", "").strip()
            tgt = record.get("target", "").strip()
            if src and tgt:
                contents.append(types.Content(role="user", parts=[types.Part(text=src)]))
                contents.append(types.Content(role="model", parts=[types.Part(text=tgt)]))

        contents.append(types.Content(role="user", parts=[types.Part(text=text.strip())]))

        logger.info(f"TranscreationService [style_guide={style_guide.name}]: calling {model} for '{pair}'")
        await asyncio.sleep(4)
        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            ),
        )
        result = response.text.strip()
        logger.info(f"TranscreationService [style_guide={style_guide.name}]: received {len(result)} chars.")
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_style_guide_prompt(self, guide, source_lang: str, target_lang: str) -> str:
        register_descriptions = {
            "FORMAL": "Use formal register throughout. Avoid contractions and colloquialisms.",
            "INFORMAL": "Use informal, conversational register. Contractions and natural speech are appropriate.",
            "NEUTRAL": "Use neutral register — neither overly formal nor casual.",
            "TECHNICAL": "Use precise technical language. Prioritise accuracy and clarity over style.",
            "COLLOQUIAL": "Use natural colloquial language as a native speaker would in casual conversation.",
        }
        tone_descriptions = {
            "AUTHORITATIVE": "authoritative and confident — speak with expertise and certainty",
            "PLAYFUL": "playful and light — use energy and approachable language",
            "APPROACHABLE": "warm, friendly, and accessible",
            "BOLD": "bold and direct — short sentences, strong verbs, no hedging",
            "WARM": "warm and empathetic — prioritise connection over information",
            "PRECISE": "measured and precise — every word earns its place",
        }

        register_str = register_descriptions.get(str(guide.styleRegister), "")
        tone_str = tone_descriptions.get(str(guide.tone), "") if guide.tone else ""

        required_terms = [t for t in (guide.terms or []) if str(t.type) == "REQUIRED"]
        forbidden_terms = [t for t in (guide.terms or []) if str(t.type) == "FORBIDDEN"]

        lines = [
            f"You are a translation specialist adapting {source_lang.upper()} text into {target_lang.upper()}.",
            f"Apply the style guide: {guide.name}.",
            "",
            "STYLE CONSTRAINTS:",
            f"- Register: {register_str}",
        ]
        if tone_str:
            lines.append(f"- Tone: {tone_str}")
        if guide.rules:
            lines.append("- Rules:")
            for rule in guide.rules:
                lines.append(f"  • {rule}")
        if required_terms:
            terms_str = ", ".join(
                f"{t.term}" + (f" → {t.targetTerm}" if t.targetTerm else "") for t in required_terms
            )
            lines.append(f"- Required terms (must appear in output): {terms_str}")
        if forbidden_terms:
            lines.append(f"- Forbidden terms (must NOT appear): {', '.join(t.term for t in forbidden_terms)}")
        lines += [
            "",
            "Do not add explanations, alternatives, or any text other than the translation.",
        ]
        return "\n".join(lines)
