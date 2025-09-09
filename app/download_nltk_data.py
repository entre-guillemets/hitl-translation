import nltk
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Download NLTK 'punkt' tokenizer if not already present."""
    try:
        # Check if the 'punkt' tokenizer is available
        nltk.data.find('tokenizers/punkt')
        logger.info("NLTK 'punkt' tokenizer already exists. No download needed.")
    except nltk.downloader.DownloadError:
        # If not, download it to the default user directory
        logger.info("NLTK 'punkt' tokenizer not found. Downloading...")
        try:
            nltk.download('punkt')
            logger.info("Download of 'punkt' successful!")
        except Exception as e:
            logger.error(f"Failed to download NLTK 'punkt' tokenizer: {e}")
            logger.error("Please run the following command manually:")
            logger.error("python -m nltk.downloader punkt")

if __name__ == "__main__":
    main()