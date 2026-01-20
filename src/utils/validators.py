"""
Модуль валидации данных.
"""
import re
import logging
from datetime import datetime
import wx


def validate_full_name(name):
    """Валидация полного имени (ФИО)"""
    if not name or not isinstance(name, str):
        return False, "Имя не может быть пустым"
    name = name.strip()
    if len(name) < 3 or len(name) > 255:
        return False, "Имя должно быть от 3 до 255 символов"
    # Проверка на допустимые символы: буквы, пробелы, дефисы, точки
    if not re.match(r'^[А-ЯЁа-яёA-Za-z\s\-\.,]+$', name):
        return False, "Имя может содержать только буквы, пробелы, дефисы и точки"
    return True, None


def validate_title(title):
    """Валидация названия"""
    if not title or not isinstance(title, str):
        return False, "Название не может быть пустым"
    title = title.strip()
    if len(title) < 2 or len(title) > 255:
        return False, "Название должно быть от 2 до 255 символов"
    return True, None


def validate_year(year):
    """Валидация года"""
    if year is None or year == '':
        return True, None  # Год необязателен
    try:
        year_int = int(year) if isinstance(year, str) else year
        if year_int < 1000 or year_int > datetime.now().year + 10:
            return False, f"Год должен быть от 1000 до {datetime.now().year + 10}"
        return True, None
    except (ValueError, TypeError):
        return False, "Год должен быть числом"


def validate_date(date_str):
    """Валидация даты в формате YYYY-MM-DD"""
    if not date_str:
        return True, None  # Дата необязательна
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        min_date = datetime(1900, 1, 1)
        max_date = datetime(2100, 12, 31)
        if date_obj < min_date or date_obj > max_date:
            return False, "Дата должна быть между 1900-01-01 и 2100-12-31"
        return True, None
    except ValueError:
        return False, "Неверный формат даты. Используйте YYYY-MM-DD"


def validate_datetime(datetime_str):
    """Валидация даты и времени в формате YYYY-MM-DD HH:MM:SS"""
    if not datetime_str:
        return False, "Дата и время обязательны"
    try:
        dt_obj = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        min_dt = datetime(1900, 1, 1, 0, 0, 0)
        max_dt = datetime(2100, 12, 31, 23, 59, 59)
        if dt_obj < min_dt or dt_obj > max_dt:
            return False, "Дата и время должны быть между 1900-01-01 00:00:00 и 2100-12-31 23:59:59"
        return True, None
    except ValueError:
        return False, "Неверный формат даты и времени. Используйте YYYY-MM-DD HH:MM:SS"


def validate_capacity(capacity):
    """Валидация вместимости"""
    if capacity is None or capacity == '':
        return True, None  # Вместимость необязательна
    try:
        cap_int = int(capacity) if isinstance(capacity, str) else capacity
        if cap_int <= 0 or cap_int > 100000:
            return False, "Вместимость должна быть от 1 до 100000"
        return True, None
    except (ValueError, TypeError):
        return False, "Вместимость должна быть числом"


def validate_text_field(text, max_length=None, required=False):
    """Валидация текстового поля"""
    if required and (not text or not text.strip()):
        return False, "Поле обязательно для заполнения"
    if text and max_length and len(text) > max_length:
        return False, f"Текст не должен превышать {max_length} символов"
    return True, None


def show_error(message):
    """Показать диалог с ошибкой"""
    try:
        if wx.IsMainThread() and wx.GetApp():
            dialog = wx.MessageDialog(None, message, "Ошибка", wx.OK | wx.ICON_ERROR)
            dialog.ShowModal()
            dialog.Destroy()
        logging.error(f"ERROR: {message}")
    except Exception:
        logging.error(f"ERROR: {message}")


def show_success(message):
    """Показать диалог с успешным сообщением"""
    try:
        if wx.IsMainThread() and wx.GetApp():
            dialog = wx.MessageDialog(None, message, "Успех", wx.OK | wx.ICON_INFORMATION)
            dialog.ShowModal()
            dialog.Destroy()
    except Exception:
        pass


def show_confirmation(message):
    """Показать диалог подтверждения"""
    try:
        if wx.IsMainThread() and wx.GetApp():
            dialog = wx.MessageDialog(None, message, "Подтверждение", wx.YES_NO | wx.ICON_QUESTION)
            result = dialog.ShowModal()
            dialog.Destroy()
            return result == wx.ID_YES
        return False
    except Exception:
        return False


def format_date_for_display(date_value):
    """Форматирует дату для отображения в читаемом виде"""
    if not date_value:
        return ""
    try:
        if isinstance(date_value, str):
            date_obj = datetime.strptime(date_value, '%Y-%m-%d')
        elif isinstance(date_value, datetime):
            date_obj = date_value
        else:
            return str(date_value)
        return date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        return str(date_value)


def format_datetime_for_display(datetime_value):
    """Форматирует дату и время для отображения в читаемом виде"""
    if not datetime_value:
        return ""
    try:
        if isinstance(datetime_value, str):
            dt_obj = datetime.strptime(datetime_value, '%Y-%m-%d %H:%M:%S')
        elif isinstance(datetime_value, datetime):
            dt_obj = datetime_value
        else:
            return str(datetime_value)
        return dt_obj.strftime('%d.%m.%Y %H:%M')
    except (ValueError, TypeError):
        return str(datetime_value)

