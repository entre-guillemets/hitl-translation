# Multi-Engine Translation Quality Dashboard

This project provides a comprehensive platform for evaluating, comparing, and analyzing the quality of various machine translation (MT) engines. It features a robust FastAPI backend for translation and quality metric calculation, and a Next.js/React frontend with a detailed analytics dashboard.

![Quality Dashboard Screenshot](https://github.com/user-attachments/assets/9345c671-8f8d-4a35-bf3d-4fdf3a1551bb)

## Core Features

* **Multi-Engine Translation**: Supports multiple local translation models, including Helsinki-NLP (OPUS), ELAN, T5, and NLLB.
* **Pivot Translation**: Enables translation between language pairs not directly supported by a single model (e.g., Japanese to French via English).
* **Advanced Quality Metrics**: Automatically calculates standard industry metrics to evaluate post-edited translations:
    * **BLEU**: Measures precision and recall of n-grams.
    * **TER (Translation Edit Rate)**: Calculates the number of edits required to change a hypothesis to a reference.
    * **COMET**: A state-of-the-art model-based metric that uses source, hypothesis, and reference for highly accurate quality scoring.
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

### 2. Download and Place Models

**This is a critical step.** This project loads translation models from a local `models/` directory which is not checked into version control. You must manually download the required models.

1.  Create a `models` directory in the root of the project.
2.  Download the following models and place them inside the `models/` directory. Ensure the folder names inside `models/` **exactly match** the names listed below.

| Model Name in Code          | Hugging Face Repository                                                              | Target Folder Name                |
| :-------------------------- | :----------------------------------------------------------------------------------- | :-------------------------------- |
| `HELSINKI_EN_JP`/`OPUS_EN_JP` | [Helsinki-NLP/opus-mt-en-jap](https://huggingface.co/Helsinki-NLP/opus-mt-en-jap)         | `Helsinki-NLP_opus-mt-en-jap`     |
| `OPUS_JA_EN`                | [Helsinki-NLP/opus-mt-ja-en](https://huggingface.co/Helsinki-NLP/opus-mt-ja-en)           | `opus-mt-ja-en`                   |
| `ELAN_JA_EN`                | [elan-mt-bt-ja-en](https://huggingface.co/Mitsua/elan-mt-bt-ja-en/tree/main) | `Mitsua_elan-mt-bt-ja-en`       |
| `HELSINKI_EN_FR`            | [Helsinki-NLP/opus-mt-en-fr](https://huggingface.co/Helsinki-NLP/opus-mt-en-fr)           | `Helsinki-NLP_opus-mt-en-fr`      |
| `HELSINKI_FR_EN`            | [Helsinki-NLP/opus-mt-fr-en](https://huggingface.co/Helsinki-NLP/opus-mt-fr-en)           | `Helsinki-NLP_opus-mt-fr-en`      |
| `OPUS_TC_BIG_EN_FR`         | [Helsinki-NLP/opus-mt-tc-big-en-fr](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-fr) | `opus-mt-tc-big-en-fr`          |
| `T5_BASE`/`T5_MULTILINGUAL` | [google-t5/t5-base](https://huggingface.co/google-t5/t5-base)                         | `google-t5_t5-base`               |
| `NLLB_200`                  | [facebook/nllb-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M) | `nllb-200-distilled-600M`         |

*Note: You can use the "Download" button on the Hugging Face Hub page to download a zip of the repository, then unzip and rename the folder as specified above.*

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
* Statistical significance testing: P-values are currently hardcoded at 0.05 rather than calculated from actual data distributions
* Confidence interval calculations: Fixed at 0.95 instead of computed using bootstrap or t-distribution methods
* System health timestamps: Last usage times default to datetime.now() rather than actual service usage tracking
## API Consistency
* Mixed routing patterns: Frontend components use inconsistent API paths (/api/analytics/ vs /api/translation-requests/)
* Error handling: Some endpoints lack proper fallback states when external services are unavailable
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
* Add real-time polling for dashboard updates
* Cultural bias detection: Implement regex-based tone and cultural mismatch detection system
* Advanced statistical analysis: Add bootstrap confidence intervals and proper correlation significance testing
* Enhanced system monitoring: Real-time capacity tracking and utilization metrics
* Improved error handling: Graceful degradation when external services are unavailable
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
## Performance Considerations
* Large batch processing may timeout on quality assessment endpoints
* Dashboard loading times increase with historical data volume
* Real-time updates limited to 30-second intervals to prevent API overload
## 📋 Testing Status
## Fully Tested
✅ Basic COMET scoring functionality
✅ BLEU/TER calculation accuracy
✅ Database CRUD operations
✅ Multi-engine orchestration
## Partially Tested
⚠️ Statistical correlation calculations (needs validation with larger datasets)
⚠️ Cultural bias detection patterns (limited language coverage)
⚠️ System health monitoring (basic functionality only)
## Needs Testing
❌ Confidence interval calculations under various data distributions
❌ Performance under high concurrent load
❌ Error recovery when external services fail
❌ Data migration and schema updates
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
