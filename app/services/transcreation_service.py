import logging
import os
from pathlib import Path
from typing import Optional
import asyncio

import yaml
from google import genai
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
            pair = yaml_file.stem.lower()
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
        pair = f"{source_lang.lower()}-{target_lang.lower()}"
        return pair in self._profiles

    def supported_pairs(self) -> list[str]:
        return list(self._profiles.keys())

    async def transcreate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not self._client:
            raise RuntimeError("Gemini client not initialised — check GEMINI_API_KEY.")

        pair = f"{source_lang.lower()}-{target_lang.lower()}"
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
