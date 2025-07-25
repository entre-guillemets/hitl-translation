# Multi-Engine Translation Quality Dashboard

This project provides a comprehensive platform for evaluating, comparing, and analyzing the quality of various machine translation (MT) engines. It features a robust FastAPI backend for translation and quality metric calculation, and a Next.js/React frontend with a detailed analytics dashboard.

![Quality Dashboard Screenshot](https://github.com/user-attachments/assets/c6b88707-f57e-441f-a6d0-7efdb87c86b4)

## Core Features

* **Multi-Engine Translation**: Supports multiple local translation models, including Helsinki-NLP (OPUS), ELAN, T5, and NLLB.
* **Pivot Translation**: Enables translation between language pairs not directly supported by a single model (e.g., Japanese to French via English).
* **Advanced Quality Metrics**: Automatically calculates standard industry metrics to evaluate post-edited translations:
    * **BLEU**: Measures precision and recall of n-grams.
    * **TER (Translation Edit Rate)**: Calculates the number of edits required to change a hypothesis to a reference.
    * **COMET**: A state-of-the-art model-based metric that uses source, hypothesis, and reference for highly accurate quality scoring.
    * **ChrF**: A character-level F-score that is known to correlate well with human judgments, especially for languages with rich morphology or different scripts.
* **Interactive Analytics Dashboard**: A rich user interface built with Next.js, Shadcn UI, and Recharts to visualize:
    * Model performance leaderboards.
    * Post-edit quality analysis by language pair.
    * Correlation matrices between different quality scores.
    * Side-by-side diff viewer for comparing machine translations against human edits.
* **Data Persistence**: Uses a Prisma ORM with a PostgreSQL database to store all translation requests, strings, model outputs, and quality metrics.

## Tech Stack

* **Backend**: Python, FastAPI, Uvicorn
* **Frontend**: Next.js, React, TypeScript, Tailwind CSS, Shadcn/UI, Recharts
* **Machine Learning**: PyTorch, Transformers, Unbabel-COMET, Sacrebleu
* **Database**: PostgreSQL, Prisma

---

## Getting Started

### Prerequisites

* Python 3.10+
* Node.js 18+ and npm/yarn
* Git
* A running PostgreSQL database instance.
* For Japanese tokenization with `sacrebleu`, you must have MeCab installed:
    ```bash
    # On macOS
    brew install mecab mecab-ipadic
    # On Debian/Ubuntu
    sudo apt-get install mecab libmecab-dev mecab-ipadic-utf8
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
    # Note: The model_manager.py script is located in app/services/

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

3.  **Manual Placement (Alternative)**
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

    *Note: For Hugging Face models, you can use the "Download" button on the Hugging Face Hub page to download a zip of the repository, then unzip and rename the folder as specified above. COMET and MetricX models are typically managed by the Hugging Face/COMET library's internal caching mechanisms when loaded programmatically.*

### 3. Backend Setup

The backend serves the translation models and the main API.

```bash
# Navigate to the project directory
/path/to/your/download

# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install sentencepiece==0.2.0
pip install -r requirements.txt

# Set up your environment variables
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

### 5. Run the Front & Backends (using concurrently):**
```bash
npm run dev:full
```
The backend API will be available at `http://localhost:8001`.
The frontend, using Next.js and Shadcn components, will be availble typically on port `5173`. Check your terminal for the exact URL (e.g., `http://localhost:5173`).

---

## API Endpoints

The FastAPI backend provides several endpoints for debugging and interacting with the system. View the full, interactive documentation provided by Swagger UI at:

**[http://localhost:8001/docs](http://localhost:8001/docs)**

### Under Development
## 🚧 Known Issues & Limitations
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
Database Dependencies
* Some analytics require minimum data thresholds to generate meaningful insights
* Quality correlations need sufficient sample sizes for statistical validity
* System health metrics depend on active translation processing
## External Service Dependencies
* COMET model availability required for quality predictions
* Translation engines must be accessible for multi-engine orchestration

## 📋 Testing Status
## Fully Tested
✅ Basic COMET scoring functionality
✅ BLEU/TER calculation accuracy
✅ Database CRUD operations
✅ Multi-engine orchestration
## Partially Tested
⚠️ Statistical correlation calculations (needs validation with larger datasets)
## Needs Testing
❌ Confidence interval calculations under various data distributions
❌ Performance under high concurrent load
## 🎯 Contribution Areas
We welcome contributions in these areas:
* Statistical methods: Implementing robust confidence intervals and significance testing
* Cultural linguistics: Expanding bias detection patterns for additional languages
* Performance optimization: Improving batch processing and caching strategies
* Testing coverage: Adding unit tests for statistical calculations and edge cases
* Documentation: API documentation and setup guides for development environment

## Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.
