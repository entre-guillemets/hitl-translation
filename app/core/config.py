import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # CORS settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174", 
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000"
    ]
    
    # API settings
    API_TITLE: str = "Translation Management API"
    API_VERSION: str = "1.0.0"
    
    # Model paths and configurations
    MODEL_CACHE_DIR: str = os.getenv("MODEL_CACHE_DIR", "./models")
    METRICX_MODEL_PATH: str = os.getenv("METRICX_MODEL_PATH", "./models/metricx-24-hybrid-large-v2p6")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
