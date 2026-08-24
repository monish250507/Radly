import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PORT = int(os.environ.get("PORT", 5000))
    ENV = os.environ.get("NODE_ENV", "development")
    IS_PRODUCTION = ENV == "production"
    IS_VERCEL = os.environ.get("VERCEL") == "1"
    RUNTIME_MODE = "vercel-serverless" if IS_VERCEL else "standalone-node"
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").lower()
    
    class Service:
        NAME = "paperblast-impact-analyzer"
        FRIENDLY_NAME = "PaperBlast Impact Engine API"
    
    class Groq:
        API_KEY = os.environ.get("GROQ_API_KEY", "")
        CONFIGURED = bool(API_KEY)
        DEFAULT_MODEL = "llama-3.1-70b-versatile"
        MAX_RETRIES = 2
        TIMEOUT_MS = 15000

config = Config()
