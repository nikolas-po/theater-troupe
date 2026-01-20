"""
Утилиты для работы с отчетами.
"""
import os
from typing import List, Optional
from datetime import datetime


def get_reports_directory() -> str:
    """Возвращает путь к директории отчетов"""
    reports_dir = os.path.join(os.getcwd(), 'reports')
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir, exist_ok=True)
    return reports_dir


def get_available_report_formats() -> List[str]:
    """Возвращает список доступных форматов отчетов"""
    return ['PDF', 'XLSX']


def generate_report_filename(report_name: str, format_ext: str, 
                             custom_name: Optional[str] = None) -> str:
    """
    Генерирует имя файла для отчета.
    
    Args:
        report_name: Базовое имя отчета
        format_ext: Расширение файла (pdf, xlsx)
        custom_name: Пользовательское имя (опционально)
    
    Returns:
        Имя файла
    """
    if custom_name:
        if not custom_name.endswith(f'.{format_ext}'):
            return f"{custom_name}.{format_ext}"
        return custom_name
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{report_name}_{timestamp}.{format_ext}"


def ensure_directory_exists(filepath: str) -> str:
    """
    Создает директорию для файла, если она не существует.
    
    Args:
        filepath: Полный путь к файлу
    
    Returns:
        Путь к файлу
    """
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return filepath

