import re

def detokenize_japanese(text: str) -> str:
    """Remove unnecessary spaces from Japanese text output"""
    text = re.sub(r'(?<=[\u3040-\u30FF\u4E00-\u9FFF])\s+(?=[\u3040-\u30FF\u4E00-\u9FFF])', '', text)
    text = text.replace(' .', '。').replace(' ,', '、')
    text = text.replace(' ・', '・')
    text = text.replace(' ！', '！').replace(' ？', '？')
    text = re.sub(r'\s+(?=[。、・！？])', '', text)
    text = re.sub(r'\s*（\s*', '（', text)
    text = re.sub(r'\s*）\s*', '）', text)
    return text.strip()

def get_model_for_language_pair(source_lang: str, target_lang: str) -> str:
    """Get the appropriate model for a language pair with consistent mapping."""
    pair = f"{source_lang.lower()}-{target_lang.lower()}"
    
    model_mapping = {
        'en-jp': 'HELSINKI_EN_JP',
        'jp-en': 'ELAN_JA_EN',
        'en-fr': 'HELSINKI_EN_FR',
        'fr-en': 'HELSINKI_FR_EN',
        'jp-fr': 'PIVOT_ELAN_HELSINKI',
        # WMT variants
        'jpn-eng': 'ELAN_JA_EN',
        'eng-jpn': 'HELSINKI_EN_JP',
        'eng-fra': 'HELSINKI_EN_FR',
        'fra-eng': 'HELSINKI_FR_EN',
    }
    
    return model_mapping.get(pair, 'HELSINKI_EN_FR')
