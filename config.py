import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://redis:6379/0'
