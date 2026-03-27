#!/usr/bin/env python3
"""Seed sample advertiser profiles and ad copy translation strings.

Run from the project root:
    python scripts/seed_advertiser_data.py

Creates 3 advertiser profiles and 8–10 ad copy strings per profile, designed
to stress-test brand voice preservation and cultural fitness evaluation across
EN→JP and EN→FR pairs.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prisma import Prisma
from prisma.enums import BrandTone, AdRegister, SourceLanguage, MTModel, RequestType, RequestStatus


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

PROFILES = [
    {
        "brandName": "Aurient Watches",
        "brandTone": BrandTone.LUXURY,
        "adRegister": AdRegister.FORMAL,
        "targetMarkets": ["JP", "FR"],
        "keyTerms": ["Aurient", "precision", "heritage", "tourbillon"],
        "tabooTerms": ["cheap", "affordable", "discount", "sale", "deal"],
        "policyNotes": "Never use informal contractions. Avoid superlatives unless referencing craftsmanship.",
    },
    {
        "brandName": "Volta Electronics",
        "brandTone": BrandTone.TECHNICAL,
        "adRegister": AdRegister.NEUTRAL,
        "targetMarkets": ["JP", "FR"],
        "keyTerms": ["Volta", "performance", "innovation", "seamless"],
        "tabooTerms": ["complicated", "difficult", "expensive"],
        "policyNotes": "Spec claims must not be inflated. Do not promise specific battery life numbers in ad copy.",
    },
    {
        "brandName": "Breezy Home",
        "brandTone": BrandTone.APPROACHABLE,
        "adRegister": AdRegister.INFORMAL,
        "targetMarkets": ["JP", "FR"],
        "keyTerms": ["Breezy", "home", "family", "everyday"],
        "tabooTerms": ["luxury", "premium", "exclusive", "elite"],
        "policyNotes": "Keep copy warm and inclusive. Avoid any language that could exclude renters or smaller households.",
    },
]

# ---------------------------------------------------------------------------
# Ad copy strings per advertiser
# Each entry: (source_en, translated_text_placeholder, target_lang)
# translated_text is intentionally varied in quality to enable interesting
# brand voice / cultural fitness scoring.
# ---------------------------------------------------------------------------

AD_COPY = {
    "Aurient Watches": [
        # EN→JP
        ("Time, perfected over generations.", "時を超えた精度。", "JA"),
        ("Every second, a masterpiece.", "すべての秒が、傑作。", "JA"),
        ("Where heritage meets precision engineering.", "伝統と精密工学の融合。", "JA"),
        ("The art of keeping time.", "時を刻む芸術。", "JA"),
        # EN→FR — deliberately mixed quality to show scoring spread
        ("Time, perfected over generations.", "Le temps, perfectionné depuis des générations.", "FR"),
        ("Every second, a masterpiece.", "Chaque seconde, un chef-d'œuvre.", "FR"),
        ("Where heritage meets precision engineering.", "Où le patrimoine rencontre l'ingénierie de précision.", "FR"),
        # Intentionally flat/literal — should score low on cultural fitness
        ("The art of keeping time.", "L'art de garder le temps.", "FR"),
    ],
    "Volta Electronics": [
        # EN→JP
        ("Power that moves with you.", "あなたとともに動くパワー。", "JA"),
        ("Seamless performance, every time.", "いつでも、シームレスなパフォーマンス。", "JA"),
        ("Innovation you can feel.", "感じられるイノベーション。", "JA"),
        ("Built for the way you work.", "あなたの仕事スタイルに合わせた設計。", "JA"),
        # EN→FR
        ("Power that moves with you.", "Une puissance qui vous suit partout.", "FR"),
        ("Seamless performance, every time.", "Des performances sans faille, à chaque fois.", "FR"),
        # Intentionally overly literal
        ("Innovation you can feel.", "Innovation que vous pouvez sentir.", "FR"),
        ("Built for the way you work.", "Construit pour la façon dont vous travaillez.", "FR"),
    ],
    "Breezy Home": [
        # EN→JP
        ("Make every room feel like yours.", "すべての部屋を、自分だけの空間に。", "JA"),
        ("Home is where Breezy is.", "Breezyがあるところが、わが家。", "JA"),
        ("Simple ideas, better days.", "シンプルなアイデアで、もっといい毎日を。", "JA"),
        ("The little things that make a big difference.", "小さな工夫が、大きな違いを生む。", "JA"),
        # EN→FR
        ("Make every room feel like yours.", "Faites de chaque pièce votre espace.", "FR"),
        ("Home is where Breezy is.", "Là où Breezy est, c'est chez vous.", "FR"),
        ("Simple ideas, better days.", "Des idées simples pour de meilleures journées.", "FR"),
        # Intentionally too formal — register mismatch for this brand
        ("The little things that make a big difference.", "Les petits détails qui font toute la différence.", "FR"),
    ],
}


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

async def main():
    db = Prisma()
    await db.connect()

    print("Seeding advertiser profiles...")
    profile_ids: dict[str, str] = {}

    for p in PROFILES:
        # Upsert by brandName to keep the script idempotent
        existing = await db.advertiserprofile.find_first(
            where={"brandName": p["brandName"]}
        )
        if existing:
            profile_ids[p["brandName"]] = existing.id
            print(f"  ↩ {p['brandName']} already exists ({existing.id})")
            continue

        created = await db.advertiserprofile.create(data=p)
        profile_ids[p["brandName"]] = created.id
        print(f"  ✓ Created {p['brandName']} ({created.id})")

    print("\nSeeding translation requests and ad copy strings...")

    for brand_name, strings in AD_COPY.items():
        profile_id = profile_ids[brand_name]

        # One TranslationRequest per brand (groups the strings logically)
        req = await db.translationrequest.create(
            data={
                "sourceLanguage": SourceLanguage.EN,
                "targetLanguages": ["JA", "FR"],
                "languagePair": "EN-JA,EN-FR",
                "wordCount": sum(len(s[0].split()) for s in strings),
                "fileName": f"{brand_name.lower().replace(' ', '_')}_ad_copy.txt",
                "mtModel": MTModel.GEMINI_TRANSCREATION,
                "requestType": RequestType.SINGLE_ENGINE,
                "status": RequestStatus.COMPLETED,
                "advertiserProfileId": profile_id,
            }
        )
        print(f"  ✓ Request {req.id} for {brand_name}")

        for source_en, translated, target_lang in strings:
            ts = await db.translationstring.create(
                data={
                    "sourceText": source_en,
                    "translatedText": translated,
                    "targetLanguage": target_lang,
                    "translationRequestId": req.id,
                    "translationType": "STANDARD",
                    "status": "REVIEWED",
                    "isApproved": True,
                }
            )
            print(f"    + [{target_lang}] \"{source_en[:40]}\"")

    await db.disconnect()
    print("\nDone. Run the LLM judge brand-voice evaluation to score these strings.")


if __name__ == "__main__":
    asyncio.run(main())
