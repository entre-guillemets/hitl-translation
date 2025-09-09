# Multi-Engine Translation Quality Dashboard with Multimodal OCR

This project provides a comprehensive platform for evaluating, comparing, and analyzing the quality of various machine translation (MT) engines. It features a robust FastAPI backend for translation and quality metric calculation, **multimodal content extraction with OCR and transcription capabilities**, and a Next.js/React frontend with a detailed analytics dashboard.

![Quality Dashboard Screenshot](https://github.com/user-attachments/assets/c6b88707-f57e-441f-a6d0-7efdb87c86b4)

## Core Features

### Translation & Quality Analysis
* **Multi-Engine Translation**: Supports multiple local translation models, including Helsinki-NLP (OPUS), ELAN, T5, and NLLB.
* **Pivot Translation**: Enables translation between language pairs not directly supported by a single model (e.g., Japanese to French via English).
* **Advanced Quality Metrics**: Automatically calculates standard industry metrics to evaluate post-edited translations:
    * **BLEU**: Measures precision and recall of n-grams.
    * **TER (Translation Edit Rate)**: Calculates the number of edits required to change a hypothesis to a reference.
    * **COMET**: A state-of-the-art model-based metric that uses source, hypothesis, and reference for highly accurate quality scoring.
    * **ChrF**: A character-level F-score that is known to correlate well with human judgments, especially for languages with rich morphology or different scripts.

### 🆕 Multimodal Content Extraction
* **Image OCR**: Extract text from images with automatic language detection
    * **Specialized Japanese OCR**: Uses Manga OCR for Japanese text with fallback to Tesseract
    * **Multi-language Support**: Tesseract-based OCR for English, French, and other languages
    * **Intelligent Preprocessing**: Automatic image enhancement for better OCR accuracy
* **PDF Processing**: Extract text from both text-based and scanned PDFs
    * **Hybrid Approach**: Direct text extraction for digital PDFs, OCR for scanned pages
    * **Multi-page Support**: Process entire documents with page-by-page analysis
* **Audio Transcription**: Convert speech to text using OpenAI Whisper
    * **Language Detection**: Automatic audio language identification
    * **Multiple Formats**: Support for various audio file types
* **Smart Language Detection**: Automatic detection of content language across all input types
    * **Character-based Detection**: Special handling for Japanese character recognition
    * **Coherence Validation**: Ensures detected languages match actual content

### Analytics & Visualization
* **Interactive Analytics Dashboard**: A rich user interface built with Next.js, Shadcn UI, and Recharts to visualize:
    * Model performance leaderboards.
    * Post-edit quality analysis by language pair.
    * Correlation matrices between different quality scores.
    * Side-by-side diff viewer for comparing machine translations against human edits.
* **Data Persistence**: Uses a Prisma ORM with a PostgreSQL database to store all translation requests, strings, model outputs, and quality metrics.

## Tech Stack

### Backend
* **Core**: Python, FastAPI, Uvicorn
* **Machine Learning**: PyTorch, Transformers, Unbabel-COMET, Sacrebleu
* **OCR & Multimodal**: 
    * Tesseract (via pytesseract)
    * Manga OCR for Japanese text
    * OpenAI Whisper for audio transcription
    * PDFplumber for PDF processing
    * OpenCV and PIL for image processing
* **Language Detection**: langdetect, custom Japanese character detection

### Frontend
* **Framework**: Next.js, React, TypeScript
* **Styling**: Tailwind CSS, Shadcn/UI
* **Visualization**: Recharts

### Database
* **ORM**: Prisma
* **Database**: PostgreSQL

---

## Getting Started

### Prerequisites

* Python 3.10+
* Node.js 18+ and npm/yarn
* Git
* A running PostgreSQL database instance
* **System Dependencies**:
    * **Tesseract OCR**: Required for text extraction from images
        ```bash
        # On macOS
        brew install tesseract tesseract-lang
        # On Debian/Ubuntu  
        sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-jpn
        # On Windows
        # Download from: https://github.com/UB-Mannheim/tesseract/wiki
        ```
    * **MeCab**: Required for Japanese tokenization with `sacrebleu`
        ```bash
        # On macOS
        brew install mecab mecab-ipadic
        # On Debian/Ubuntu
        sudo apt-get install mecab libmecab-dev mecab-ipadic-utf8
        ```
    * **FFmpeg**: Required for audio processing with Whisper
        ```bash
        # On macOS
        brew install ffmpeg
        # On Debian/Ubuntu
        sudo apt-get install ffmpeg
        ```

### 1. Clone the Repository

```bash
git clone git@github.com:entre-guillemets/hitl-translation.git
cd hitl-translation
```

### 2. Download and Prepare Models

**This is a critical step.** This project loads translation models from a local `models/` directory which is not checked into version control due to their large size. You must download and place the required models before running the application.

We provide a convenient script to automate this process.

1.  **Automated Download (Recommended)**
    Use the provided `model_manager.py` script to download all necessary models directly into your project's `models/` directory. This script handles the correct naming and placement for you.
    *Note: The model_manager.py script is located in app/services/*

    ```bash
    # Ensure you are in the project root directory
    python app/services/model_manager.py --download-all
    ```
    *   **Note:** This process will download several gigabytes of data and may take a considerable amount of time (20-60 minutes or more) depending on your internet connection.
    *   You can check the status of your models at any time:
        ```bash
        python app/services/model_manager.py --status
        ```
    *   If you only need a specific model, you can download it individually (e.g., for `T5_BASE`):
        ```bash
        python app/services/model_manager.py --download mt5_multilingual
        ```
        (Refer to the `model_manager.py` source or run `python app/services/model_manager.py --list` for all model keys.)

2.  **Manual Placement (Alternative)**
    If you prefer to manually manage your models, or already have them downloaded, you can place them directly into a `models/` directory in the root of your project. Ensure the folder names inside `models/` **exactly match** the names listed below.

    | Model Name in Code          | Hugging Face Repository                                                              | Target Folder Name                |
    | :-------------------------- | :----------------------------------------------------------------------------------- | :-------------------------------- |
    | `HELSINKI_EN_JP`/`OPUS_EN_JP` | [Helsinki-NLP/opus-mt-en-jap](https://huggingface.co/Helsinki-NLP/opus-mt-en-jap)         | `Helsinki-NLP_opus-mt-en-jap`     |
    | `OPUS_JA_EN`                | [Helsinki-NLP/opus-mt-ja-en](https://huggingface.co/Helsinki-NLP/opus-mt-ja-en)           | `opus-mt-ja-en`                   |
    | `ELAN_JA_EN`                | [Mitsua/elan-mt-bt-ja-en](https://huggingface.co/Mitsua/elan-mt-bt-ja-en/tree/main) | `Mitsua_elan-mt-bt-ja-en`       |
    | `HELSINKI_EN_FR`            | [Helsinki-NLP/opus-mt-en-fr](https://huggingface.co/Helsinki-NLP/opus-mt-en-fr)           | `Helsinki-NLP_opus-mt-en-fr`      |
    | `HELSINKI_FR_EN`            | [Helsinki-NLP/opus-mt-fr-en](https://huggingface.co/Helsinki-NLP/opus-mt-fr-en)           | `Helsinki-NLP_opus-mt-fr-en`      |
    | `OPUS_TC_BIG_EN_FR`         | [Helsinki-NLP/opus-mt-tc-big-en-fr](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-fr) | `opus-mt-tc-big-en-fr`          |
    | `T5_BASE`/`T5_MULTILINGUAL` | [google-t5/t5-base](https://huggingface.co/google-t5/t5-base)                         | `google-t5_t5-base`               |
    | `NLLB_200`                  | [facebook/nllb-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M) | `nllb-200-distilled-600M`         |
    | `COMET`                     | [Unbabel/wmt22-comet-da](https://huggingface.co/Unbabel/wmt22-comet-da)                 | *(Managed by Hugging Face cache)* |
    | `MetricX`                   | [google/metricx-24-hybrid-large-v2p6](https://huggingface.co/google/metricx-24-hybrid-large-v2p6) | *(Managed by Hugging Face cache)* |
    | `Manga OCR`                 | [kha-white/manga-ocr-base](https://huggingface.co/kha-white/manga-ocr-base)               | *(Managed by Hugging Face cache)* |
    | `Whisper`                   | OpenAI Whisper models (base, small, medium, large) | *(Managed by Whisper library cache)* |

    *Note: For Hugging Face models, you can use the "Download" button on the Hugging Face Hub page to download a zip of the repository, then unzip and rename the folder as specified above. COMET, MetricX, Manga OCR, and Whisper models are typically managed by their respective libraries' internal caching mechanisms when loaded programmatically.*

### 3. Backend Setup

The backend serves the translation models, multimodal processing, and the main API.

```bash
# Navigate to the project directory
/path/to/your/download

# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install sentencepiece==0.2.0
pip install -r requirements.txt
```

**Additional dependencies for multimodal features:**
```bash
# OCR and image processing
pip install pytesseract opencv-python pillow pdfplumber

# Japanese OCR (optional but recommended for Japanese content)
pip install manga-ocr

# Audio transcription (optional but recommended for audio content)  
pip install openai-whisper

# Language detection
pip install langdetect
```

**Set up your environment variables:**
```bash
cp .env.example .env
```

Edit the `.env` file with your PostgreSQL database connection string and the following details:

```env
DATABASE_URL="postgresql://user:password@localhost:5432/mydb"
REACT_APP_API_URL="http://localhost:8001"
FUZZY_MATCH_THRESHOLD=0.6
AUTO_TM_CREATION=true
TRANSFORMERS_CACHE=./models
HF_HOME=./models
PYTORCH_TRANSFORMERS_CACHE=./models
LOG_LEVEL=INFO
TRANSFORMERS_TRUST_REMOTE_CODE=1

# Optional: Tesseract path (if not in system PATH)
# TESSERACT_CMD=/usr/local/bin/tesseract
```

**Initialize the Database:**
Run the Prisma command to push the schema to your database.
```bash
python -m prisma db push
```

### 4. Frontend Setup

The frontend is the Next.js quality dashboard with Shadcn components.

```bash
# Install Node.js dependencies
npm install
```

### 5. Run the Front & Backends (using concurrently)

```bash
npm run dev:full
```
The backend API will be available at `http://localhost:8001`.
The frontend, using Next.js and Shadcn components, will be available typically on port `5173`. Check your terminal for the exact URL (e.g., `http://localhost:5173`).

---

## API Endpoints

The FastAPI backend provides several endpoints for debugging and interacting with the system. View the full, interactive documentation provided by Swagger UI at:

**[http://localhost:8001/docs](http://localhost:8001/docs)**

### 🆕 Multimodal Endpoints
* `POST /api/extract-text`: Extract text from uploaded files (images, PDFs, audio)
* `POST /api/detect-language`: Detect language from multimodal content
* `POST /api/translate-file`: Upload and translate content from files

### Translation Endpoints
* `POST /api/translate`: Translate text between supported language pairs
* `GET /api/translation-requests`: Retrieve translation history and metrics

### Usage Examples

**Extract text from an image:**
```bash
curl -X POST "http://localhost:8001/api/extract-text" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@screenshot.png"
```

**Translate content from a PDF:**
```bash
curl -X POST "http://localhost:8001/api/translate-file" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "target_language=fr"
```

---

## Supported File Types

### Images
* **Formats**: PNG, JPEG, GIF, BMP, TIFF
* **OCR Engines**: 
  * Tesseract (multi-language)
  * Manga OCR (specialized for Japanese)
* **Languages**: English, French, Japanese, and others supported by Tesseract

### Documents  
* **PDF**: Both text-based and scanned documents
* **Text Files**: Plain text in various encodings

### Audio
* **Formats**: MP3, WAV, M4A, FLAC, and other formats supported by FFmpeg
* **Transcription**: OpenAI Whisper with automatic language detection
* **Languages**: 99+ languages supported by Whisper

---

## Architecture Overview

### Multimodal Processing Pipeline

1. **File Upload**: Accept various file types through FastAPI endpoints
2. **Content Detection**: Automatic MIME type and language detection
3. **Specialized Processing**:
   - **Images**: Language detection → Preprocessing → OCR (Manga OCR for Japanese, Tesseract for others)
   - **PDFs**: Text extraction → OCR for scanned pages → Content assembly  
   - **Audio**: Whisper transcription with language detection
4. **Post-processing**: Text cleanup, normalization, and optional LLM enhancement
5. **Translation**: Processed text fed into existing translation pipeline

### File Processing Classes

* `MultimodalService`: Main orchestrator for all file processing
* `ImageProcessor`: Image preprocessing and enhancement for OCR
* `TextProcessor`: Post-OCR text cleanup and normalization
* `LanguageDetector`: Multi-modal language detection
* `TesseractOCREngine`: General-purpose OCR with multiple language support
* `MangaOCREngine`: Specialized Japanese text recognition

---

## Performance Considerations

### OCR Optimization
* **Image Preprocessing**: Automatic scaling and enhancement for better accuracy
* **Multiple PSM Modes**: Tesseract uses different page segmentation modes for optimal results
* **Language-specific Handling**: Japanese text uses specialized spacing fixes

### Memory Management  
* **Streaming Processing**: Large files processed in chunks where possible
* **Temporary File Cleanup**: Automatic cleanup of temporary files for audio processing
* **Model Caching**: OCR and Whisper models cached in memory for faster processing

### Error Handling
* **Graceful Fallbacks**: Multiple OCR engines with fallback strategies
* **Comprehensive Logging**: Detailed error logging for debugging multimodal processing
* **Format Validation**: Input validation for supported file types and sizes

---

## Under Development
## 🚧 Known Issues & Limitations

### Multimodal Processing
* **Large File Support**: Memory constraints for very large PDF or audio files
* **OCR Accuracy**: Accuracy depends on image quality, font, and language complexity
* **Audio Quality**: Transcription accuracy varies with audio clarity and background noise
* **Language Detection**: May struggle with mixed-language content or short text snippets

## Data & Analytics
* Placeholder data replacement: Several analytics endpoints currently return hardcoded values (p-values, confidence intervals, correlation coefficients) instead of calculated statistics

## API Consistency
* Mixed routing patterns: Frontend components use inconsistent API paths (/api/analytics/ vs /api/translation-requests/)
* Data source indicators: Dashboard doesn't clearly distinguish between real data and placeholder/sample data

## Quality Metrics
* Inter-rater agreement: Currently shows placeholder values; needs implementation when multiple reviewers are available
* TM time savings: Calculations are estimated rather than based on actual processing time differences
* Model utilization rates: Simple ratio calculations rather than capacity-based utilization metrics

## 🔄 Planned Improvements

### Multimodal Enhancements
* **Batch Processing**: Support for multiple file uploads and batch processing
* **Advanced OCR**: Integration with cloud OCR services for improved accuracy
* **Format Support**: Additional file formats (DOCX, PPTX, video subtitles)
* **Real-time Processing**: WebSocket support for real-time transcription and translation
* **Quality Metrics**: OCR confidence scores and transcription reliability indicators

### System Improvements
* Replace all hardcoded statistical values with real calculations
* Implement proper confidence interval computation using scipy.stats
* Add data source badges to distinguish API data from fallback samples
* Standardize API routing patterns across all frontend components
* Cultural bias detection: Implement regex-based tone and cultural mismatch detection system
* Advanced statistical analysis: Add bootstrap confidence intervals and proper correlation significance testing
* Multi-annotator support: Inter-rater agreement calculations for quality assessment
* Advanced bias detection: Move beyond regex to ML-based cultural adaptation metrics
* Performance optimization: Batch processing for large-scale quality assessments
* Extended language support: Additional language-specific quality metrics and cultural markers

## ⚠️ Current Limitations

### Database Dependencies
* Some analytics require minimum data thresholds to generate meaningful insights
* Quality correlations need sufficient sample sizes for statistical validity
* System health metrics depend on active translation processing

### External Service Dependencies
* COMET model availability required for quality predictions
* Translation engines must be accessible for multi-engine orchestration
* Tesseract and system dependencies must be properly installed
* Sufficient disk space required for model caching and temporary file processing

### Hardware Requirements
* **Memory**: At least 8GB RAM recommended for processing large files and models
* **Storage**: 10GB+ free space for model downloads and temporary file processing
* **CPU**: Multi-core processor recommended for efficient OCR and transcription

---

## 📋 Testing Status

## Fully Tested
✅ Basic COMET scoring functionality
✅ BLEU/TER calculation accuracy  
✅ Database CRUD operations
✅ Multi-engine orchestration
✅ Image OCR with Tesseract and Manga OCR
✅ PDF text extraction and OCR fallback
✅ Audio transcription with Whisper
✅ Language detection across modalities

## Partially Tested
⚠️ Statistical correlation calculations (needs validation with larger datasets)
⚠️ Large file processing (memory and performance limits)
⚠️ Edge cases in multimodal language detection

## Needs Testing
❌ Confidence interval calculations under various data distributions
❌ Performance under high concurrent load
❌ Batch multimodal processing
❌ Error recovery in multimodal pipeline
❌ Cross-platform compatibility of system dependencies

---

## 🎯 Contribution Areas
We welcome contributions in these areas:
* **Multimodal Processing**: Improving OCR accuracy, adding new file format support, optimizing processing pipelines
* **Statistical Methods**: Implementing robust confidence intervals and significance testing
* **Cultural Linguistics**: Expanding bias detection patterns for additional languages
* **Performance Optimization**: Improving batch processing and caching strategies for multimodal content
* **Testing Coverage**: Adding unit tests for statistical calculations, multimodal processing, and edge cases
* **Documentation**: API documentation and setup guides for development environment
* **Mobile Support**: Optimizing multimodal processing for mobile file uploads
* **Accessibility**: Ensuring OCR and transcription outputs are accessible

---

## Troubleshooting

### Common Issues

**Tesseract not found:**
```bash
# Make sure Tesseract is installed and in PATH
which tesseract
# If not found, install using package manager or set TESSERACT_CMD environment variable
```

**Japanese OCR not working:**
```bash
# Install Japanese language data for Tesseract
sudo apt-get install tesseract-ocr-jpn  # Ubuntu/Debian
brew install tesseract-lang            # macOS
```

**Whisper transcription fails:**
```bash
# Install FFmpeg if not present
brew install ffmpeg                    # macOS  
sudo apt-get install ffmpeg           # Ubuntu/Debian
```

**Memory issues with large files:**
- Consider processing files in smaller chunks
- Increase available RAM or use swap space
- Monitor memory usage during processing

---

## Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.