"""
Конфигурация базы данных.
"""
import os
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Конфигурация базы данных
DB_CONFIG: Dict[str, Any] = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'nikd'),
    'db': os.getenv('DB_NAME', 'nik'),
    'charset': 'utf8mb4',
}

