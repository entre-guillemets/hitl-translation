import re
import nltk
from nltk.tokenize import sent_tokenize
import logging

logger = logging.getLogger(__name__)

# Download required NLTK data at module initialization
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    logger.info("Downloading NLTK punkt_tab data...")
    nltk.download('punkt_tab', quiet=True)

# Alternative: If punkt_tab isn't available, try punkt
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    logger.info("Downloading NLTK punkt data...")
    nltk.download('punkt', quiet=True)

def split_text_into_sentences(text: str, source_lang: str) -> list[str]:
    """
    Splits a raw text string into a list of sentences, handling different languages.
    This function is more robust than simple split() for handling punctuation and
    newlines from various sources like images, PDFs, or audio transcription.
    """
    if not text:
        return []

    if source_lang.upper() in ['JA', 'JP']:
        sentences = re.split(r'(?<=[。！？])\s*', text.strip())
        return [s for s in sentences if s]
    else:
        try:
            # Map language codes to NLTK language names
            lang_map = {
                'EN': 'english',
                'FR': 'french',
                'ES': 'spanish',
                'DE': 'german',
                'IT': 'italian',
                'PT': 'portuguese',
                'NL': 'dutch',
                'RU': 'russian'
            }
            
            nltk_lang = lang_map.get(source_lang.upper(), 'english')
            sentences = sent_tokenize(text, language=nltk_lang)
            return [s.strip() for s in sentences if s.strip()]
        except Exception as e:
            logger.error(f"NLTK sentence tokenization failed for language '{source_lang}': {e}. Falling back to simple split.")
            sentences = re.split(r'(?<=[.!?])\s*', text.strip())
            return [s.strip() for s in sentences if s.strip()]


import re

def detokenize_japanese(text: str) -> str:
    """
    Removes unwanted spaces from Japanese text that are artifacts of tokenization.
    It removes spaces between Japanese characters and before punctuation.
    """
    if not text:
        return text

    # Remove spaces around Japanese punctuation
    text = re.sub(r'\s*([。、！？：；])\s*', r'\1', text)

    # Remove spaces between Japanese characters (Kanji, Hiragana, Katakana)
    # This pattern matches any Japanese character followed by one or more spaces
    # and replaces it with just the Japanese character.
    japanese_char_pattern = r'([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF])\s+'
    text = re.sub(japanese_char_pattern, r'\1', text)
    
    # Remove multiple consecutive spaces that might remain
    text = re.sub(r'\s+', ' ', text)

    return text.strip()

def get_model_for_language_pair(source_lang: str, target_lang: str) -> str:
    """Get the appropriate model for a language pair with consistent mapping."""
    
    # Normalize to lowercase
    source = source_lang.lower()
    target = target_lang.lower()
    
    # Handle JP/JA variations
    if source == "jp": source = "ja"
    if target == "jp": target = "ja"
    
    pair = f"{source}-{target}"
    
    model_mapping = {
        'en-ja': 'HELSINKI_EN_JA',
        'ja-en': 'OPUS_JA_EN',
        'en-fr': 'HELSINKI_EN_FR',
        'fr-en': 'HELSINKI_FR_EN',
        'ja-fr': 'PIVOT_ELAN_HELSINKI',
        'fr-ja': 'PIVOT_ELAN_HELSINKI',  
    }
    
    return model_mapping.get(pair, 'HELSINKI_EN_FR')