import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(env_file)

environment = env("DJANGO_ENVIRONMENT", default="development")

if environment == "production":
    from .production import *
elif environment == "development":
    from .development import *
else:
    raise ValueError(f"Unknown DJANGO_ENVIRONMENT='{environment}'")