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

    def _build_profile_system_prompt(self, profile, source_lang: str, target_lang: str) -> str:
        """Build a dynamic Gemini system prompt from an AdvertiserProfile."""
        tone_descriptions = {
            "AUTHORITATIVE": "authoritative and confident — speak with expertise and certainty",
            "PLAYFUL": "playful and fun — use wordplay, light humour, and energy",
            "LUXURY": "elevated and understated — suggest quality through restraint, not hyperbole",
            "APPROACHABLE": "warm, friendly, and accessible — speak like a trusted friend",
            "TECHNICAL": "precise and informative — prioritise clarity and accuracy over flair",
            "BOLD": "bold and direct — short sentences, strong verbs, no hedging",
        }
        register_descriptions = {
            "FORMAL": "Use formal register throughout. Avoid contractions and colloquialisms.",
            "INFORMAL": "Use informal, conversational register. Contractions and natural speech are appropriate.",
            "NEUTRAL": "Use neutral register — neither overly formal nor casual.",
        }

        tone_str = tone_descriptions.get(str(profile.brandTone), str(profile.brandTone).lower())
        register_str = register_descriptions.get(str(profile.adRegister), "")
        key_terms = list(profile.keyTerms or [])
        taboo_terms = list(profile.tabooTerms or [])

        lines = [
            f"You are a transcreation specialist adapting {source_lang.upper()} ad copy into {target_lang.upper()} "
            f"for {profile.brandName}.",
            "",
            "BRAND IDENTITY:",
            f"- Tone: {tone_str}",
            f"- {register_str}",
        ]
        if key_terms:
            lines.append(f"- Key terms to preserve or adapt appropriately: {', '.join(key_terms)}")
        if taboo_terms:
            lines.append(f"- Terms to NEVER use in output: {', '.join(taboo_terms)}")
        if profile.policyNotes:
            lines.append(f"- Policy constraints: {profile.policyNotes}")
        lines += [
            "",
            "Your goal is cultural and emotional adaptation, not word-for-word translation. "
            f"Every output must feel native to the target market while unmistakably sounding like {profile.brandName}.",
            "",
            "Do not add explanations, alternative options, or any text other than the transcreated output.",
        ]
        return "\n".join(lines)

    async def transcreate_with_profile(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        profile,
    ) -> str:
        """Transcreate using a dynamic system prompt built from an AdvertiserProfile.

        Falls back to the static YAML golden records for few-shot examples if a
        profile exists for this language pair, so prior examples still help the model.
        If no YAML profile exists for the pair, runs with the dynamic prompt alone.
        """
        if not self._client:
            raise RuntimeError("Gemini client not initialised — check GEMINI_API_KEY.")

        pair = normalize_lang_pair(f"{source_lang}-{target_lang}")
        yaml_profile = self._profiles.get(pair)  # may be None — that's OK

        system_prompt = self._build_profile_system_prompt(profile, source_lang, target_lang)
        golden_records = (yaml_profile or {}).get("golden_records") or []
        model = (yaml_profile or {}).get("model", DEFAULT_MODEL)

        contents: list[types.Content] = []
        for record in golden_records:
            src = record.get("source", "").strip()
            tgt = record.get("target", "").strip()
            if src and tgt:
                contents.append(types.Content(role="user", parts=[types.Part(text=src)]))
                contents.append(types.Content(role="model", parts=[types.Part(text=tgt)]))

        contents.append(types.Content(role="user", parts=[types.Part(text=text.strip())]))

        logger.info(
            f"TranscreationService [profile={profile.brandName}]: calling {model} for '{pair}' "
            f"({len(golden_records)} golden records, {len(text)} chars)"
        )
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
        logger.info(f"TranscreationService [profile={profile.brandName}]: received {len(result)} chars for '{pair}'.")
        return result

    async def transcreate_with_corrective_feedback(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        profile,
        feedback: str,
        prior_translation: str,
    ) -> str:
        """Re-transcreate using a corrective feedback turn.

        Builds the same few-shot context as transcreate_with_profile, then
        appends the prior translation as a model turn followed by a user
        correction turn so Gemini can incorporate the feedback on the next try.
        """
        if not self._client:
            raise RuntimeError("Gemini client not initialised — check GEMINI_API_KEY.")

        pair = normalize_lang_pair(f"{source_lang}-{target_lang}")
        yaml_profile = self._profiles.get(pair)

        system_prompt = self._build_profile_system_prompt(profile, source_lang, target_lang)
        golden_records = (yaml_profile or {}).get("golden_records") or []
        model = (yaml_profile or {}).get("model", DEFAULT_MODEL)

        contents: list[types.Content] = []
        for record in golden_records:
            src = record.get("source", "").strip()
            tgt = record.get("target", "").strip()
            if src and tgt:
                contents.append(types.Content(role="user", parts=[types.Part(text=src)]))
                contents.append(types.Content(role="model", parts=[types.Part(text=tgt)]))

        # Original source → prior model output → corrective user turn
        contents.append(types.Content(role="user", parts=[types.Part(text=text.strip())]))
        contents.append(types.Content(role="model", parts=[types.Part(text=prior_translation.strip())]))
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=f"That translation needs improvement. {feedback} Please provide a revised version.")],
        ))

        logger.info(
            f"TranscreationService [profile={profile.brandName}]: corrective feedback call "
            f"to {model} for '{pair}' ({len(text)} chars)"
        )
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
        logger.info(f"TranscreationService [profile={profile.brandName}]: corrective result {len(result)} chars for '{pair}'.")
        return result

    async def transcreate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not self._client:
            raise RuntimeError("Gemini client not initialised — check GEMINI_API_KEY.")

        pair = normalize_lang_pair(f"{source_lang}-{target_lang}")
        profile = self._profiles.get(pair)
        if not profile:
            raise ValueError(f"No transcreation profile for pair '{pair}'.")

        system_prompt = profile.get("system_prompt", "").strip()
        golden_records = profile.get("golden_records") or []
        model = profile.get("model", DEFAULT_MODEL)

        # Build few-shot contents: alternating user/model turns from golden records
        contents: list[types.Content] = []
        for record in golden_records:
            src = record.get("source", "").strip()
            tgt = record.get("target", "").strip()
            if src and tgt:
                contents.append(types.Content(role="user", parts=[types.Part(text=src)]))
                contents.append(types.Content(role="model", parts=[types.Part(text=tgt)]))

        # Append the actual request
        contents.append(types.Content(role="user", parts=[types.Part(text=text.strip())]))

        logger.info(
            f"TranscreationService: calling {model} for '{pair}' "
            f"({len(golden_records)} golden records, {len(text)} chars)"
        )
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
