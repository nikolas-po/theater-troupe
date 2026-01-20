"""
Основной модуль театральной системы управления.
"""
import wx
import wx.grid as gridlib
import logging
from datetime import datetime
import asyncio
import aiomysql
import threading
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import re
import os
import sys

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Импорт модулей проекта
from config.database import DB_CONFIG
from src.database.connection import DatabaseManager
from src.utils.theme import ThemeManager, theme_manager
from src.utils.validators import (
    validate_full_name, validate_title, validate_year,
    validate_date, validate_datetime, validate_capacity,
    show_error, show_success, show_confirmation,
    format_date_for_display, format_datetime_for_display
)

# Настройка логирования
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('theatre_system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Важные сообщения о запуске логируем явно
logging.warning("=" * 60)
logging.warning("Запуск театральной системы управления")
logging.warning(f"Конфигурация БД: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}, db={DB_CONFIG['db']}")
logging.warning("=" * 60)

db_manager = None
event_loop = None
db_initialized = False

line_chart_data = []
pie_chart_data = []

# ThemeManager и DatabaseManager импортируются из соответствующих модулей

def run_event_loop():
    global event_loop, db_manager, db_initialized
    try:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        db_manager = DatabaseManager(event_loop)
        
        success = event_loop.run_until_complete(db_manager.init_pool())
        db_initialized = success
        
        if success:
            logging.warning("База данных успешно инициализирована")
            event_loop.run_forever()
        else:
            logging.error("Не удалось инициализировать базу данных")
    except Exception as e:
        logging.error(f"Ошибка в цикле событий: {e}")
        db_initialized = False
    finally:
        if event_loop and not event_loop.is_closed():
            event_loop.close()

def run_async(coro):
    if not db_initialized:
        return None
        
    if event_loop and event_loop.is_running():
        try:
            future = asyncio.run_coroutine_threadsafe(coro, event_loop)
            return future
        except Exception as e:
            logging.error(f"Ошибка запуска асинхронной операции: {e}")
            return None
    else:
        return None

metrics_data = {
    'total_rehearsals': 0,
    'actors_count': 0,
    'productions_count': 0,
    'roles_count': 0
}

rehearsals_data = []

filters = {
    'period': 'весь',
    'theatre': 'все',
    'director': 'все'
}

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def log_action(action, level=logging.INFO):
    logging.log(level, f"USER_ACTION: {action}")

# Функции валидации теперь импортируются из src.validators
# Старые определения удалены

# ========== УТИЛИТЫ ДЛЯ АВТОЗАПОЛНЕНИЯ И ВАЛИДАЦИИ ==========

class AutoCompleteDateCtrl(wx.TextCtrl):
    # Поле ввода даты с автоматическим форматированием: ГГГГ-ММ-ДД
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.Bind(wx.EVT_CHAR, self.on_char)
        self.Bind(wx.EVT_TEXT, self.on_text)
        self.Bind(wx.EVT_SET_FOCUS, self.on_focus)
        self.SetHint("ГГГГ-ММ-ДД (введите цифры, разделители добавятся автоматически)")
        self._updating = False
        
    def on_focus(self, event):
        if not self.GetValue():
            self.SetValue("____-__-__")
            self.SetInsertionPoint(0)
        event.Skip()
        
    def on_char(self, event):
        key_code = event.GetKeyCode()
        cursor_pos = self.GetInsertionPoint()
        value = self.GetValue()
        digits = re.sub(r'\D', '', value)
        
        if key_code in (wx.WXK_TAB, wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_HOME, wx.WXK_END):
            event.Skip()
            return
        
        # Запрещаем удаление разделителей
        if key_code in (wx.WXK_BACK, wx.WXK_DELETE):
            if cursor_pos > 0 and cursor_pos <= len(value):
                # Проверяем, не пытаемся ли удалить разделитель
                if cursor_pos > 0 and value[cursor_pos - 1] in '-':
                    # Пропускаем разделитель и удаляем предыдущий символ
                    if cursor_pos > 1:
                        self.SetInsertionPoint(cursor_pos - 2)
                        # Удаляем символ перед разделителем
                        new_value = value[:cursor_pos-2] + value[cursor_pos:]
                        digits = re.sub(r'\D', '', new_value)
                        self._updating = True
                        try:
                            # Переформатируем
                            formatted = "____-__-__"
                            if len(digits) >= 1:
                                formatted = digits[0] + "___-__-__"
                            if len(digits) >= 2:
                                formatted = digits[0:2] + "__-__-__"
                            if len(digits) >= 3:
                                formatted = digits[0:3] + "_-__-__"
                            if len(digits) >= 4:
                                formatted = digits[0:4] + "-__-__"
                            if len(digits) >= 5:
                                formatted = digits[0:4] + "-" + digits[4] + "_-__"
                            if len(digits) >= 6:
                                formatted = digits[0:4] + "-" + digits[4:6] + "-__"
                            if len(digits) >= 7:
                                formatted = digits[0:4] + "-" + digits[4:6] + "-" + digits[6] + "_"
                            if len(digits) >= 8:
                                formatted = digits[0:4] + "-" + digits[4:6] + "-" + digits[6:8]
                            self.SetValue(formatted)
                            new_pos = max(0, cursor_pos - 2)
                            if new_pos < len(formatted) and formatted[new_pos] in '-':
                                new_pos = max(0, new_pos - 1)
                            self.SetInsertionPoint(min(new_pos, len(formatted)))
                        finally:
                            self._updating = False
                    event.Skip(False)
                    return
            event.Skip()
            return
        
        if key_code < 127:
            char = chr(key_code) if key_code < 256 else ''
            if char.isdigit():
                if len(digits) >= 8:
                    event.Skip(False)
                    return
                event.Skip()
                return
        
        event.Skip()
    
    def on_text(self, event):
        if self._updating:
            event.Skip()
            return
            
        self._updating = True
        try:
            value = self.GetValue()
            digits = re.sub(r'\D', '', value)
            
            if len(digits) > 8:
                digits = digits[:8]
            
            formatted = "____-__-__"
            if len(digits) >= 1:
                formatted = digits[0] + "___-__-__"
            if len(digits) >= 2:
                formatted = digits[0:2] + "__-__-__"
            if len(digits) >= 3:
                formatted = digits[0:3] + "_-__-__"
            if len(digits) >= 4:
                formatted = digits[0:4] + "-__-__"
            if len(digits) >= 5:
                formatted = digits[0:4] + "-" + digits[4] + "_-__"
            if len(digits) >= 6:
                formatted = digits[0:4] + "-" + digits[4:6] + "-__"
            if len(digits) >= 7:
                formatted = digits[0:4] + "-" + digits[4:6] + "-" + digits[6] + "_"
            if len(digits) >= 8:
                formatted = digits[0:4] + "-" + digits[4:6] + "-" + digits[6:8]
            
            cursor_pos = self.GetInsertionPoint()
            self.SetValue(formatted)
            
            new_pos = min(cursor_pos, len(formatted))
            if new_pos < len(formatted) and formatted[new_pos] in '-':
                new_pos += 1
            self.SetInsertionPoint(min(new_pos, len(formatted)))
        finally:
            self._updating = False
        event.Skip()
    
    def get_date_value(self):
        value = re.sub(r'\D', '', self.GetValue())
        if len(value) == 8:
            return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
        elif len(value) == 6:
            return f"{value[:4]}-{value[4:6]}-01"
        elif len(value) == 4:
            return f"{value[:4]}-01-01"
        return None
    
    def is_valid(self):
        """Проверяет валидность даты через стандартный парсер Python"""
        value = self.get_date_value()
        if not value:
            return False
        try:
            datetime.strptime(value, '%Y-%m-%d')
            return True
        except:
            return False

class AutoCompleteDateTimeCtrl(wx.TextCtrl):
    """Поле ввода даты и времени с автоматическим форматированием: YYYY-MM-DD HH:MM:SS"""
    def __init__(self, parent, *args, **kwargs):
        # Извлекаем value из kwargs, если он есть
        initial_value = kwargs.pop('value', '')
        super().__init__(parent, *args, **kwargs)
        self.Bind(wx.EVT_CHAR, self.on_char)
        self.Bind(wx.EVT_TEXT, self.on_text)
        self.Bind(wx.EVT_SET_FOCUS, self.on_focus)
        self.SetHint("YYYY-MM-DD HH:MM:SS (введите цифры, разделители добавятся автоматически)")
        self._updating = False
        
        # Если передан начальный value, устанавливаем его в правильном формате
        if initial_value:
            self.set_datetime_value(initial_value)
        
    def set_datetime_value(self, datetime_str):
        """Устанавливает значение в формате YYYY-MM-DD HH:MM:SS"""
        if not datetime_str:
            return
        
        # Парсим различные форматы даты
        try:
            if isinstance(datetime_str, str):
                # Пробуем разные форматы
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y%m%d%H%M%S']:
                    try:
                        dt = datetime.strptime(datetime_str, fmt)
                        formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                        self._updating = True
                        try:
                            wx.TextCtrl.SetValue(self, formatted)
                        finally:
                            self._updating = False
                        return
                    except:
                        continue
                # Если это только цифры, форматируем их
                digits = re.sub(r'\D', '', datetime_str)
                if len(digits) >= 8:
                    if len(digits) >= 14:
                        formatted = f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}:{digits[12:14]}"
                    elif len(digits) >= 12:
                        formatted = f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}:00"
                    elif len(digits) >= 10:
                        formatted = f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:00:00"
                    else:
                        formatted = f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]} 00:00:00"
                    self._updating = True
                    try:
                        wx.TextCtrl.SetValue(self, formatted)
                    finally:
                        self._updating = False
        except Exception as e:
            logging.error(f"Ошибка установки значения даты: {e}")
        
    def on_focus(self, event):
        value = self.GetValue()
        if not value or value.strip() == '':
            self.SetValue("")
            self.SetInsertionPoint(0)
        event.Skip()
        
    def on_char(self, event):
        key_code = event.GetKeyCode()
        cursor_pos = self.GetInsertionPoint()
        value = self.GetValue()
        
        if key_code in (wx.WXK_TAB, wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_HOME, wx.WXK_END):
            event.Skip()
            return
        
        # Обработка удаления - удаляем цифры, но не разделители
        if key_code in (wx.WXK_BACK, wx.WXK_DELETE):
            event.Skip(False)  # Всегда обрабатываем сами
            
            # Определяем позицию удаляемой цифры
            if key_code == wx.WXK_BACK:
                # Backspace - удаляем символ перед курсором
                if cursor_pos == 0:
                    return
                delete_pos = cursor_pos - 1
            else:
                # Delete - удаляем символ после курсора
                if cursor_pos >= len(value):
                    return
                delete_pos = cursor_pos
            
            # Если пытаемся удалить разделитель - переходим к предыдущей цифре
            if delete_pos < len(value) and value[delete_pos] in '- :':
                # Находим предыдущую цифру
                pos = delete_pos - 1
                while pos >= 0 and value[pos] in '- :':
                    pos -= 1
                if pos >= 0:
                    delete_pos = pos
                else:
                    return  # Нет цифр для удаления
            
            # Извлекаем все цифры из текущего значения
            digits = re.sub(r'\D', '', value)
            
            # Определяем, какую цифру удаляем
            digit_positions = []
            for i, char in enumerate(value):
                if char.isdigit():
                    digit_positions.append(i)
            
            # Находим индекс удаляемой цифры в списке цифр
            digit_index = -1
            for idx, pos in enumerate(digit_positions):
                if pos == delete_pos:
                    digit_index = idx
                    break
            
            if digit_index == -1:
                # Не нашли цифру для удаления
                return
            
            # Удаляем цифру из строки цифр
            new_digits = digits[:digit_index] + digits[digit_index + 1:]
            
            # Переформатируем строку
            if len(new_digits) == 0:
                formatted = ""
                new_pos = 0
            elif len(new_digits) <= 4:
                formatted = new_digits + "-"
                # Позиция курсора: после последней цифры или на разделителе
                new_pos = len(new_digits)
            elif len(new_digits) <= 6:
                formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-"
                # Позиция: после удаленной цифры, но с учетом разделителей
                if digit_index < 4:
                    new_pos = digit_index
                elif digit_index < 6:
                    new_pos = digit_index + 1  # +1 для первого '-'
                else:
                    new_pos = len(formatted)
            elif len(new_digits) <= 8:
                formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} "
                if digit_index < 4:
                    new_pos = digit_index
                elif digit_index < 6:
                    new_pos = digit_index + 1
                elif digit_index < 8:
                    new_pos = digit_index + 2
                else:
                    new_pos = len(formatted)
            elif len(new_digits) <= 10:
                formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} {new_digits[8:10]}:"
                if digit_index < 4:
                    new_pos = digit_index
                elif digit_index < 6:
                    new_pos = digit_index + 1
                elif digit_index < 8:
                    new_pos = digit_index + 2
                elif digit_index < 10:
                    new_pos = digit_index + 3
                else:
                    new_pos = len(formatted)
            elif len(new_digits) <= 12:
                formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} {new_digits[8:10]}:{new_digits[10:12]}:"
                if digit_index < 4:
                    new_pos = digit_index
                elif digit_index < 6:
                    new_pos = digit_index + 1
                elif digit_index < 8:
                    new_pos = digit_index + 2
                elif digit_index < 10:
                    new_pos = digit_index + 3
                elif digit_index < 12:
                    new_pos = digit_index + 4
                else:
                    new_pos = len(formatted)
            else:
                formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} {new_digits[8:10]}:{new_digits[10:12]}:{new_digits[12:14]}"
                if digit_index < 4:
                    new_pos = digit_index
                elif digit_index < 6:
                    new_pos = digit_index + 1
                elif digit_index < 8:
                    new_pos = digit_index + 2
                elif digit_index < 10:
                    new_pos = digit_index + 3
                elif digit_index < 12:
                    new_pos = digit_index + 4
                elif digit_index < 14:
                    new_pos = digit_index + 5
                else:
                    new_pos = len(formatted)
            
            # Устанавливаем новое значение
            self._updating = True
            try:
                wx.TextCtrl.SetValue(self, formatted)
                # Устанавливаем курсор в правильную позицию
                # Если курсор попадает на разделитель, перемещаем его к ближайшей цифре
                if new_pos < len(formatted) and formatted[new_pos] in '- :':
                    # При Backspace перемещаемся назад к цифре
                    if key_code == wx.WXK_BACK:
                        while new_pos > 0 and (formatted[new_pos - 1] in '- :' or new_pos >= len(formatted)):
                            new_pos -= 1
                    else:
                        # При Delete перемещаемся вперед к цифре
                        while new_pos < len(formatted) and formatted[new_pos] in '- :':
                            new_pos += 1
                # Ограничиваем позицию длиной строки
                new_pos = max(0, min(new_pos, len(formatted)))
                self.SetInsertionPoint(new_pos)
            finally:
                self._updating = False
            
            return
        
        # Обработка ввода цифр - сразу форматируем
        if key_code < 127:
            char = chr(key_code) if key_code < 256 else ''
            if char.isdigit():
                digits = re.sub(r'\D', '', value)
                if len(digits) >= 14:
                    event.Skip(False)
                    return
                
                # Определяем, в какое поле вставлять цифру на основе позиции курсора
                # Формат: YYYY-MM-DD HH:MM:SS
                # Позиции: 0123-45-67 89:01:23
                
                # Определяем индекс вставки в строке цифр на основе позиции курсора
                insert_index = len(digits)  # По умолчанию в конец
                
                # Анализируем текущую позицию курсора в отформатированной строке
                if cursor_pos <= len(value):
                    # Подсчитываем количество цифр до позиции курсора
                    digits_before_cursor = 0
                    for i in range(min(cursor_pos, len(value))):
                        if value[i].isdigit():
                            digits_before_cursor += 1
                    
                    # Определяем позицию вставки на основе текущей позиции курсора
                    if cursor_pos < len(value):
                        if value[cursor_pos].isdigit():
                            # Курсор на цифре - вставляем перед этой цифрой
                            insert_index = digits_before_cursor
                        elif value[cursor_pos] in '- :':
                            # Курсор на разделителе - вставляем после последней цифры перед разделителем
                            insert_index = digits_before_cursor
                        else:
                            # Курсор между символами - используем количество цифр до курсора
                            insert_index = digits_before_cursor
                    else:
                        # Курсор в конце строки - вставляем в конец
                        insert_index = len(digits)
                    
                    # Если курсор сразу после разделителя, вставляем в начало следующего поля
                    if cursor_pos > 0 and cursor_pos <= len(value) and value[cursor_pos - 1] in '- :':
                        insert_index = digits_before_cursor
                
                # Вставляем цифру в нужную позицию
                if insert_index >= len(digits):
                    new_digits = digits + char
                else:
                    new_digits = digits[:insert_index] + char + digits[insert_index:]
                
                if len(new_digits) > 14:
                    new_digits = new_digits[:14]
                
                # Форматируем сразу
                if len(new_digits) <= 4:
                    formatted = new_digits + "-"
                elif len(new_digits) <= 6:
                    formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-"
                elif len(new_digits) <= 8:
                    formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} "
                elif len(new_digits) <= 10:
                    formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} {new_digits[8:10]}:"
                elif len(new_digits) <= 12:
                    formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} {new_digits[8:10]}:{new_digits[10:12]}:"
                else:
                    formatted = f"{new_digits[0:4]}-{new_digits[4:6]}-{new_digits[6:8]} {new_digits[8:10]}:{new_digits[10:12]}:{new_digits[12:14]}"
                
                # Вычисляем новую позицию курсора - после вставленной цифры
                new_digit_positions = []
                for i, c in enumerate(formatted):
                    if c.isdigit():
                        new_digit_positions.append(i)
                
                # Позиция курсора - сразу после вставленной цифры
                if insert_index < len(new_digit_positions):
                    new_pos = new_digit_positions[insert_index] + 1
                else:
                    # Если вставили в конец
                    new_pos = len(formatted)
                
                # Если курсор попадает на разделитель, перемещаем его вперед
                if new_pos < len(formatted) and formatted[new_pos] in '- :':
                    new_pos += 1
                
                # Автоматический переход к следующему полю только при полном заполнении
                # (не при редактировании в середине)
                if len(new_digits) == 4 and insert_index == 3:  # Заполнили год полностью
                    new_pos = 5
                elif len(new_digits) == 6 and insert_index == 5:  # Заполнили месяц полностью
                    new_pos = 8
                elif len(new_digits) == 8 and insert_index == 7:  # Заполнили день полностью
                    new_pos = 11
                elif len(new_digits) == 10 and insert_index == 9:  # Заполнили час полностью
                    new_pos = 14
                elif len(new_digits) == 12 and insert_index == 11:  # Заполнили минуту полностью
                    new_pos = 17
                elif len(new_digits) == 14 and insert_index == 13:  # Заполнили секунду полностью
                    new_pos = 19
                
                # Устанавливаем отформатированное значение
                self._updating = True
                try:
                    wx.TextCtrl.SetValue(self, formatted)
                    # Ограничиваем позицию длиной строки
                    new_pos = max(0, min(new_pos, len(formatted)))
                    self.SetInsertionPoint(new_pos)
                finally:
                    self._updating = False
                
                event.Skip(False)
                return
        
        # Запрещаем ввод нецифровых символов (кроме навигации)
        if key_code < 127:
            char = chr(key_code) if key_code < 256 else ''
            if char and not char.isdigit():
                event.Skip(False)
                return
        
        event.Skip()
    
    def on_text(self, event):
        if self._updating:
            event.Skip()
            return
            
        # Этот метод вызывается после on_char, но мы уже обработали ввод в on_char
        # Поэтому здесь просто пропускаем событие, чтобы не дублировать обработку
        event.Skip()
    
    def SetValue(self, value):
        """Переопределяем SetValue для правильной обработки формата YYYY-MM-DD HH:MM:SS"""
        if value:
            self.set_datetime_value(value)
        else:
            super().SetValue("")
    
    def get_datetime_value(self):
        """Возвращает значение в формате YYYY-MM-DD HH:MM:SS"""
        value = self.GetValue()
        if not value:
            return None
        
        # Извлекаем цифры и форматируем
        digits = re.sub(r'\D', '', value)
        if len(digits) >= 14:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}:{digits[12:14]}"
        elif len(digits) >= 12:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}:00"
        elif len(digits) >= 10:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:00:00"
        elif len(digits) >= 8:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]} 00:00:00"
        elif len(digits) == 6:
            return f"{digits[:4]}-{digits[4:6]}-01 00:00:00"
        elif len(digits) == 4:
            return f"{digits[:4]}-01-01 00:00:00"
        
        # Если значение уже в правильном формате, возвращаем его
        if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', value):
            return value
        
        return None
    
    def is_valid(self):
        """Проверяет валидность даты и времени"""
        value = self.get_datetime_value()
        if not value:
            return False
        try:
            datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            return True
        except:
            return False

class ValidatedTextCtrl(wx.TextCtrl):
    """Текстовое поле с валидацией"""
    def __init__(self, parent, validator_func=None, error_message="", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.validator_func = validator_func
        self.error_message = error_message
        self.is_valid_state = True
        self.last_error = ""
        self.Bind(wx.EVT_TEXT, self.on_text_change)
        self.Bind(wx.EVT_KILL_FOCUS, self.on_lose_focus)
        self.SetToolTip(error_message if error_message else "Введите корректное значение")
        
    def on_text_change(self, event):
        self.validate()
        event.Skip()
    
    def on_lose_focus(self, event):
        was_valid = self.is_valid_state
        self.validate()
        # Если поле стало невалидным при потере фокуса - показываем сообщение
        if not self.is_valid_state and was_valid and self.last_error:
            wx.CallAfter(lambda: show_error(f"Ошибка ввода: {self.last_error}"))
        event.Skip()
    
    def validate(self):
        value = self.GetValue()
        if self.validator_func:
            try:
                self.is_valid_state = self.validator_func(value)
                if not self.is_valid_state:
                    self.last_error = self.error_message
            except Exception as e:
                self.is_valid_state = False
                self.last_error = str(e) if str(e) else self.error_message
        else:
            self.is_valid_state = len(value.strip()) > 0
            if not self.is_valid_state:
                self.last_error = "Поле не может быть пустым"
        
        theme = theme_manager.get_theme()
        if self.is_valid_state:
            self.SetBackgroundColour(theme['text_ctrl_bg'])
            self.SetToolTip("")
        else:
            self.SetBackgroundColour(wx.Colour(255, 200, 200))
            tooltip_text = self.last_error if self.last_error else self.error_message
            self.SetToolTip(tooltip_text)
        self.Refresh()
        return self.is_valid_state
    
    def is_valid(self):
        return self.validate()
    
    def get_error_message(self):
        """Получить сообщение об ошибке"""
        return self.last_error if not self.is_valid_state else ""


class ComboTextCtrl(wx.ComboBox):
    """Упрощенная версия на основе wx.ComboBox - стабильнее чем ComboCtrl"""
    
    def __init__(self, parent, choices=None, *args, **kwargs):
        style = kwargs.pop('style', wx.CB_DROPDOWN)
        super().__init__(parent, style=style, choices=choices or [], *args, **kwargs)
        self.choices = choices or []
        self.SetMinSize((200, -1))
        
        # Для автодополнения
        self.Bind(wx.EVT_TEXT, self.on_text_change)
    
    def on_text_change(self, event):
        """Базовая фильтрация вариантов"""
        # Не обрабатываем событие, если значение устанавливается программно
        if hasattr(self, '_setting_value') and self._setting_value:
            event.Skip()
            return
            
        current_text = self.GetValue().lower()
        if current_text and self.choices:
            filtered = [choice for choice in self.choices if current_text in choice.lower()]
            self.SetItems(filtered[:20])
        else:
            self.SetItems(self.choices[:20])
        
        self.Popup() if current_text and self.GetCount() > 0 else self.Dismiss()
        event.Skip()
    
    def SetValue(self, value):
        """Переопределяем SetValue, чтобы предотвратить стирание при программной установке"""
        self._setting_value = True
        try:
            super().SetValue(str(value) if value else '')
        finally:
            self._setting_value = False
    
    def set_choices(self, choices):
        """Устанавливает список вариантов"""
        self.choices = choices
        self.SetItems(choices[:20])
    
    def get_value(self):
        return self.GetValue().strip()
    
    def is_valid(self):
        value = self.get_value()
        return len(value) > 0

class ValidatedDialog(wx.Dialog):
    def __init__(self, parent, title, size=None):
        if size:
            super().__init__(parent, title=title, size=size,
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        else:
            super().__init__(parent, title=title,
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.validated_fields = []
        self.ok_button = None
        self.required_fields = []
        self.error_labels = {}
        wx.CallAfter(self._apply_theme_delayed)
    
    def _apply_theme_delayed(self):
        theme_manager.apply_theme(self)
        
    def add_validated_field(self, field, validator_func=None, required=False, error_label=None):
        """Добавить поле для валидации
        required: True если поле обязательное
        error_label: wx.StaticText для отображения ошибки
        """
        self.validated_fields.append({
            'field': field,
            'validator': validator_func,
            'required': required
        })
        if required:
            self.required_fields.append(field)
        if error_label:
            self.error_labels[field] = error_label
        
        if isinstance(field, (wx.TextCtrl, ComboTextCtrl, AutoCompleteDateCtrl, AutoCompleteDateTimeCtrl)) or hasattr(field, 'GetValue'):
            try:
                field.Bind(wx.EVT_TEXT, lambda e: self.validate_all())
                field.Bind(wx.EVT_KILL_FOCUS, lambda e: self.validate_all())
            except:
                pass
        elif isinstance(field, wx.Choice):
            try:
                field.Bind(wx.EVT_CHOICE, lambda e: self.validate_all())
            except:
                pass
        elif hasattr(field, 'Bind'):
            try:
                field.Bind(wx.EVT_COMBOBOX, lambda e: self.validate_all())
            except:
                pass
    
    def validate_all(self):
        """Валидирует все зарегистрированные поля и обновляет кнопку OK.
        Логика валидации зависит от типа поля:
        - Поля с методом is_valid() - используют его
        - wx.Choice - проверяют что выбран элемент (GetSelection() != wx.NOT_FOUND)
        - Остальные поля - проверяют что есть значение (или используют кастомный валидатор)
        Визуальная обратная связь: белый фон = валидно, красный = невалидно"""
        all_valid = True
        error_messages = []
        
        for item in self.validated_fields:
            field = item['field']
            validator = item['validator']
            required = item.get('required', False)
            is_valid = False
            error_msg = ""
            
            try:
                # Приоритет 1: встроенный метод is_valid (для кастомных полей типа AutoCompleteDateCtrl)
                if hasattr(field, 'is_valid'):
                    is_valid = field.is_valid()
                    if not is_valid and hasattr(field, 'get_error_message'):
                        error_msg = field.get_error_message()
                # Приоритет 2: Choice элементы (выпадающие списки)
                elif isinstance(field, wx.Choice):
                    if validator:
                        is_valid = validator(field.GetSelection())
                    else:
                        # По умолчанию: проверяем что что-то выбрано
                        is_valid = field.GetSelection() != wx.NOT_FOUND
                    if not is_valid and required:
                        error_msg = "Обязательное поле"
                # Приоритет 3: есть кастомный валидатор
                elif validator:
                    if isinstance(field, wx.Choice):
                        is_valid = validator(field.GetSelection())
                    else:
                        value = field.GetValue() if hasattr(field, 'GetValue') else ''
                        is_valid = validator(value if not isinstance(value, int) else value)
                    if not is_valid and required:
                        error_msg = "Обязательное поле"
                # Приоритет 4: по умолчанию - проверка что поле не пустое
                else:
                    if isinstance(field, wx.Choice):
                        is_valid = field.GetSelection() != wx.NOT_FOUND
                    else:
                        value = field.GetValue() if hasattr(field, 'GetValue') else ''
                        is_valid = len(str(value).strip()) > 0
                    if not is_valid and required:
                        error_msg = "Обязательное поле"
            except Exception as e:
                logging.error(f"Ошибка валидации поля: {e}")
                is_valid = False
                if required:
                    error_msg = "Ошибка валидации"
            
            # Визуальная обратная связь: меняем цвет фона поля только если поле было проверено при попытке сохранения
            # Изначально все поля белые, красными становятся только при ошибке валидации
            if hasattr(field, 'SetBackgroundColour'):
                try:
                    if is_valid:
                        field.SetBackgroundColour(wx.Colour(255, 255, 255))  # Белый = валидно
                    # Красный фон устанавливается только в on_ok при попытке сохранения
                    field.Refresh()
                except:
                    pass
            
            # Обновляем метку ошибки
            if field in self.error_labels:
                error_label = self.error_labels[field]
                if error_label:
                    if is_valid:
                        error_label.SetLabel("")
                        error_label.SetForegroundColour(wx.Colour(0, 0, 0))
                    else:
                        error_label.SetLabel(error_msg if error_msg else "Ошибка")
                        error_label.SetForegroundColour(wx.Colour(255, 0, 0))
                    error_label.Refresh()
            
            if not is_valid:
                all_valid = False
                if error_msg:
                    error_messages.append(error_msg)
        
        # Кнопка OK активна только если все поля валидны
        if self.ok_button:
            try:
                self.ok_button.Enable(all_valid)
            except:
                pass
        
        return all_valid
    
    def on_ok(self, event):
        # Обработчик нажатия OK - проверяет валидацию перед закрытием
        if not self.validate_all():
            # Подсвечиваем все невалидные поля красным
            for item in self.validated_fields:
                field = item['field']
                validator = item['validator']
                required = item.get('required', False)
                is_valid = False
                
                try:
                    if hasattr(field, 'is_valid'):
                        is_valid = field.is_valid()
                    elif isinstance(field, wx.Choice):
                        if validator:
                            is_valid = validator(field.GetSelection())
                        else:
                            is_valid = field.GetSelection() != wx.NOT_FOUND
                    elif validator:
                        if isinstance(field, wx.Choice):
                            is_valid = validator(field.GetSelection())
                        else:
                            value = field.GetValue() if hasattr(field, 'GetValue') else ''
                            is_valid = validator(value if not isinstance(value, int) else value)
                    else:
                        if isinstance(field, wx.Choice):
                            is_valid = field.GetSelection() != wx.NOT_FOUND
                        else:
                            value = field.GetValue() if hasattr(field, 'GetValue') else ''
                            is_valid = len(str(value).strip()) > 0
                except:
                    is_valid = False
                
                # Подсвечиваем красным невалидные поля
                if not is_valid and hasattr(field, 'SetBackgroundColour'):
                    try:
                        field.SetBackgroundColour(wx.Colour(255, 200, 200))
                        field.Refresh()
                    except:
                        pass
                
                # Обновляем метку ошибки
                if field in self.error_labels:
                    error_label = self.error_labels[field]
                    if error_label:
                        if not is_valid:
                            error_label.SetForegroundColour(wx.Colour(255, 0, 0))
                            error_label.Refresh()
            
            show_error("Исправьте ошибки в полях, помеченных красным")
            return  # Не закрываем диалог
        # Если все валидно - закрываем диалог
        event.Skip()
    
    def set_ok_button(self, button):
        """Установить кнопку OK для управления"""
        self.ok_button = button
        # Привязываем обработчик, который проверяет валидацию перед закрытием
        button.Bind(wx.EVT_BUTTON, self.on_ok)
        self.validate_all()
async def get_sample_data(force_refresh=False):
    """Получение свежих данных из БД
    
    Args:
        force_refresh: Если True, принудительно обновляет данные из БД
    """
    try:
        if not db_initialized or not db_manager:
            raise RuntimeError("Диспетчер базы данных не инициализирован")
        
        # Принудительно выполняем запросы к БД
        tasks = [
            db_manager.get_all_actors(force_refresh=force_refresh),
            db_manager.get_all_authors(force_refresh=force_refresh),
            db_manager.get_all_directors(force_refresh=force_refresh),
            db_manager.get_all_plays(force_refresh=force_refresh),
            db_manager.get_all_productions(force_refresh=force_refresh),
            db_manager.get_all_performances(force_refresh=force_refresh),
            db_manager.get_all_rehearsals(force_refresh=force_refresh),
            db_manager.get_all_roles(force_refresh=force_refresh),
            db_manager.get_all_locations(force_refresh=force_refresh),
            db_manager.get_all_theatres(force_refresh=force_refresh)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        tables = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"Ошибка загрузки данных {i}: {result}")
                tables.append([])
            else:
                tables.append(result)
        
        actors, authors, directors, plays, productions, performances, rehearsals, roles, locations, theatres = tables
        
        plays_dict = {play['id']: play for play in (plays or [])}
        directors_dict = {director['id']: director for director in (directors or [])}
        locations_dict = {location['id']: location for location in (locations or [])}
        productions_dict = {production['id']: production for production in (productions or [])}
        
        tables_data = {
            "Актеры": [
                [actor['id'], actor['full_name'], actor['experience']] 
                for actor in (actors or [])
            ],
            "Авторы": [
                [author['id'], author['full_name'], author['biography']] 
                for author in (authors or [])
            ],
            "Пьесы": [
                [play['id'], play['title'], play['genre'], play['year_written'], play['description']] 
                for play in (plays or [])
            ],
            "Режиссеры": [
                [director['id'], director['full_name'], director['biography']] 
                for director in (directors or [])
            ],
            "Постановки": [
                [production['id'], production['title'], format_date_for_display(production['production_date']), 
                 production['description'], 
                 plays_dict.get(production['play_id'], {}).get('title', 'Неизвестно') if production.get('play_id') else '',
                 directors_dict.get(production['director_id'], {}).get('full_name', 'Неизвестно') if production.get('director_id') else ''] 
                for production in (productions or [])
            ],
            "Спектакли": [
                [performance['id'], format_datetime_for_display(performance['datetime']), 
                 f"{locations_dict.get(performance['location_id'], {}).get('theatre_name', '')}, {locations_dict.get(performance['location_id'], {}).get('hall_name', '')}" if performance.get('location_id') and locations_dict.get(performance['location_id']) else 'Неизвестно',
                 productions_dict.get(performance['production_id'], {}).get('title', 'Неизвестно') if performance.get('production_id') else ''] 
                for performance in (performances or [])
            ],
            "Репетиции": [
                [rehearsal['id'], format_datetime_for_display(rehearsal['datetime']), 
                 f"{locations_dict.get(rehearsal['location_id'], {}).get('theatre_name', '')}, {locations_dict.get(rehearsal['location_id'], {}).get('hall_name', '')}" if rehearsal.get('location_id') and locations_dict.get(rehearsal['location_id']) else 'Неизвестно',
                 productions_dict.get(rehearsal['production_id'], {}).get('title', 'Неизвестно') if rehearsal.get('production_id') else ''] 
                for rehearsal in (rehearsals or [])
            ],
            "Роли": [
                [role['id'], role['title'], role['description'], 
                 plays_dict.get(role['play_id'], {}).get('title', 'Неизвестно') if role.get('play_id') else ''] 
                for role in (roles or [])
            ],
            "Локации": [
                [location['id'], f"{location.get('theatre_name', '')}, {location.get('hall_name', '')}", 
                 location.get('city') or '', location.get('street') or '', 
                 location.get('house_number') or '', location.get('postal_code') or '',
                 location.get('capacity') or ''] 
                for location in (locations or [])
            ],
            "Театры": [
                [theatre['id'], theatre['name'], 
                 theatre.get('city') or '', theatre.get('street') or '', 
                 theatre.get('house_number') or '', theatre.get('postal_code') or ''] 
                for theatre in (theatres or [])
            ]
        }
        
        table_headers = {
            "Актеры": ["ID", "ФИО актера", "Опыт и портфолио"],
            "Авторы": ["ID", "ФИО автора", "Биография"],
            "Пьесы": ["ID", "Название пьесы", "Жанр", "Год написания", "Описание"],
            "Режиссеры": ["ID", "ФИО режиссера", "Биография"],
            "Постановки": ["ID", "Название постановки", "Дата постановки", "Описание", "Пьеса", "Режиссер"],
            "Спектакли": ["ID", "Дата и время", "Место проведения", "Постановка"],
            "Репетиции": ["ID", "Дата и время", "Место проведения", "Постановка"],
            "Роли": ["ID", "Название роли", "Описание роли", "Пьеса"],
            "Локации": ["ID", "Название", "Город", "Улица", "Дом", "Индекс", "Вместимость"],
            "Театры": ["ID", "Название театра", "Город", "Улица", "Дом", "Индекс"]
        }
        
        return tables_data, table_headers
    except Exception as e:
        logging.error(f"Ошибка получения данных: {e}")
        show_error(f"Ошибка загрузки данных: {e}")
        return {}, {}

# Флаг для предотвращения множественных одновременных обновлений
_refresh_in_progress = False

async def refresh_all_data():
    """Полное обновление всех данных из базы с учетом фильтров"""
    global metrics_data, rehearsals_data, line_chart_data, pie_chart_data, _refresh_in_progress
    
    if _refresh_in_progress:
        logging.warning("Обновление уже выполняется, пропускаем дублирующий запрос")
        return False
    
    _refresh_in_progress = True
    try:
        if not db_initialized or not db_manager:
            logging.error("База данных не инициализирована")
            return False
            
        # Не логируем начало обновления (слишком часто)
        
        # Получаем текущие фильтры
        current_filters = filters.copy() if filters else {}
        
        actors_task = db_manager.get_all_actors()
        productions_task = db_manager.get_all_productions()
        roles_task = db_manager.get_total_roles()
        monthly_data_task = db_manager.get_rehearsals_by_month(current_filters)
        genre_data_task = db_manager.get_plays_by_genre()
        filtered_rehearsals_count_task = db_manager.get_filtered_rehearsals_count(current_filters)
        
        actors, productions, roles_count, monthly_data, genre_data, filtered_rehearsals_count = await asyncio.gather(
            actors_task, productions_task, roles_task, monthly_data_task, genre_data_task, filtered_rehearsals_count_task,
            return_exceptions=True
        )
        
        if isinstance(actors, Exception):
            logging.error(f"Ошибка загрузки актеров: {actors}")
            actors = []
        if isinstance(productions, Exception):
            logging.error(f"Ошибка загрузки постановок: {productions}")
            productions = []
        if isinstance(roles_count, Exception):
            logging.error(f"Ошибка загрузки количества ролей: {roles_count}")
            roles_count = 0
        if isinstance(monthly_data, Exception):
            logging.error(f"Ошибка загрузки месячных данных: {monthly_data}")
            monthly_data = []
        if isinstance(genre_data, Exception):
            logging.error(f"Ошибка загрузки данных по жанрам: {genre_data}")
            genre_data = []
        if isinstance(filtered_rehearsals_count, Exception):
            logging.error(f"Ошибка загрузки количества репетиций: {filtered_rehearsals_count}")
            filtered_rehearsals_count = 0
        
        # Метрики с учетом фильтров
        metrics_data = {
            'total_rehearsals': filtered_rehearsals_count if not isinstance(filtered_rehearsals_count, Exception) else 0,
            'actors_count': len(actors) if actors else 0,
            'productions_count': len(productions) if productions else 0,
            'roles_count': roles_count if not isinstance(roles_count, Exception) else 0
        }
        
        line_chart_data = monthly_data if monthly_data and not isinstance(monthly_data, Exception) else []
        pie_chart_data = genre_data if genre_data and not isinstance(genre_data, Exception) else []
        
        # Загружаем репетиции для таблицы
        upcoming_rehearsals = await db_manager.get_upcoming_rehearsals(10, current_filters)
        rehearsals_data = []
        
        if upcoming_rehearsals and not isinstance(upcoming_rehearsals, Exception):
            # Загружаем количество актеров для всех репетиций одним запросом
            rehearsal_ids = [r['id'] for r in upcoming_rehearsals if r.get('id')]
            actors_counts = {}
            if rehearsal_ids:
                # Загружаем все количества актеров на репетициях одним запросом
                placeholders = ','.join(['%s'] * len(rehearsal_ids))
                counts_query = await db_manager.execute_query(f"""
                    SELECT rehearsal_id, COUNT(*) as count 
                    FROM actor_rehearsal 
                    WHERE rehearsal_id IN ({placeholders})
                    GROUP BY rehearsal_id
                """, tuple(rehearsal_ids))
                actors_counts = {row['rehearsal_id']: row['count'] for row in (counts_query or [])}
            
            for rehearsal in upcoming_rehearsals:
                rehearsal_id = rehearsal.get('id')
                actors_count = actors_counts.get(rehearsal_id, 0)
                rehearsals_data.append([
                    str(rehearsal['id']),
                    format_datetime_for_display(rehearsal['datetime']),
                    rehearsal.get('play_title', 'Неизвестно'),
                    rehearsal.get('director_name', 'Неизвестно'),
                    rehearsal.get('location_name', 'Неизвестно'),
                    rehearsal.get('genre', 'Неизвестно'),
                    "2 ч 30 мин",
                    str(actors_count)
                ])
        
        # Не логируем успешное обновление (слишком часто)
        return True
            
    except Exception as e:
        logging.error(f"Ошибка обновления данных: {e}", exc_info=True)
        return False
    finally:
        _refresh_in_progress = False

async def init_sample_data():
    """Инициализация данных (для обратной совместимости)"""
    return await refresh_all_data()

def update_dashboard_data():
    """Обновление данных дашборда с принудительным обновлением интерфейса"""
    def on_complete(success):
        if success:
            wx.CallAfter(refresh_current_view)
        else:
            logging.error("Не удалось обновить данные дашборда")
    
    future = run_async(refresh_all_data())
    if future:
        future.add_done_callback(lambda f: on_complete(f.result() if not f.exception() else False))
    else:
        logging.error("Не удалось запустить обновление данных")

def refresh_after_crud():
    """Универсальная функция для обновления данных из БД и интерфейса после операций CRUD"""
    # Не логируем начало обновления после CRUD (слишком часто)
    
    async def refresh_all():
        """Обновляет все данные из БД"""
        try:
            # Небольшая задержка, чтобы БД успела обработать транзакцию
            await asyncio.sleep(0.1)
            
            # Сначала обновляем общие данные
            # Не логируем обновление данных (слишком часто)
            await refresh_all_data()
            # Не логируем успешное обновление (слишком часто)
            
            # Дополнительная задержка для гарантии
            await asyncio.sleep(0.1)
            
            return True
        except Exception as e:
            logging.error(f"Ошибка обновления данных из БД: {e}", exc_info=True)
            return False
    
    def on_complete(success):
        if success:
            # Не логируем обновление интерфейса (слишком часто)
            # Обновляем текущее представление - оно загрузит свежие данные из БД
            wx.CallAfter(refresh_current_view)
            def force_refresh():
                frame = wx.GetApp().GetTopWindow() if wx.GetApp() else None
                if frame:
                    frame.Refresh()
                    frame.Update()
            wx.CallAfter(force_refresh)
        else:
            logging.error("Не удалось обновить данные из БД")
            # Все равно пытаемся обновить интерфейс
            wx.CallAfter(refresh_current_view)
    
    future = run_async(refresh_all())
    if future:
        future.add_done_callback(lambda f: on_complete(f.result() if not f.exception() else False))
    else:
        logging.error("Не удалось запустить обновление данных")
        on_complete(False)

def refresh_current_view():
    """Обновляет текущее представление в зависимости от того, что активно"""
    try:
        app = wx.GetApp()
        if not app:
            logging.warning("Приложение не найдено")
            return
            
        frame = app.GetTopWindow()
        if not frame:
            logging.warning("Главное окно не найдено")
            return
            
        children = frame.GetChildren()
        if not children:
            logging.warning("Нет дочерних элементов в окне")
            return
            
        current_panel = children[0]
        # Не логируем текущую панель (слишком часто)
        
        if isinstance(current_panel, DashboardPanel):
            # Не логируем обновление дашборда (слишком часто)
            current_panel.refresh_all_data()
            current_panel.Layout()
            current_panel.Refresh()
            frame.Layout()
            frame.Refresh()
            # Не логируем успешное обновление дашборда (слишком часто)
        else:
            # Не логируем обновление таблицы (слишком часто)
            refreshed = False
            
            # Прямая проверка наличия метода refresh_data
            if hasattr(current_panel, 'refresh_data') and callable(getattr(current_panel, 'refresh_data', None)):
                try:
                    current_panel.refresh_data()
                    refreshed = True
                    # Не логируем вызов refresh_data (слишком часто)
                except Exception as e:
                    logging.error(f"Ошибка вызова refresh_data(): {e}", exc_info=True)
            else:
                # Поиск метода refresh_data в дочерних элементах
                def find_refresh_data(panel):
                    if hasattr(panel, 'refresh_data') and callable(getattr(panel, 'refresh_data', None)):
                        try:
                            panel.refresh_data()
                            return True
                        except Exception as e:
                            logging.error(f"Ошибка вызова refresh_data в find: {e}")
                            return False
                    
                    # Ищем grid и его родительскую панель
                    for child in panel.GetChildren():
                        if isinstance(child, wx.grid.Grid):
                            # Ищем родительскую панель с методом refresh_data
                            parent = panel
                            while parent:
                                if hasattr(parent, 'refresh_data') and callable(getattr(parent, 'refresh_data', None)):
                                    try:
                                        parent.refresh_data()
                                        return True
                                    except Exception as e:
                                        logging.error(f"Ошибка вызова refresh_data в parent: {e}")
                                parent = parent.GetParent()
                                if not parent or isinstance(parent, wx.Frame):
                                    break
                            return False
                        elif hasattr(child, 'GetChildren'):
                            if find_refresh_data(child):
                                return True
                    return False
                
                refreshed = find_refresh_data(current_panel)
            
            current_panel.Layout()
            current_panel.Refresh()
            frame.Layout()
            frame.Refresh()
            
            if refreshed:
                # Не логируем успешное обновление таблицы (слишком часто)
                pass
            else:
                logging.warning("Не удалось найти метод refresh_data для таблицы - попытка принудительного обновления")
                # Принудительное обновление через перезагрузку данных
                try:
                    # Пытаемся найти grid и обновить его напрямую
                    for child in current_panel.GetChildren():
                        if isinstance(child, wx.grid.Grid):
                            # Найдем панель таблицы и вызовем refresh_data через замыкание
                            logging.warning("Grid найден, но refresh_data не найден - требуется перезагрузка таблицы")
                            break
                except Exception as e:
                    logging.error(f"Ошибка принудительного обновления: {e}")
    except Exception as e:
        logging.error(f"Ошибка обновления представления: {e}", exc_info=True)

class EditActorDialog(ValidatedDialog):
    def __init__(self, parent, title, actor_data=None):
        super().__init__(parent, title, size=(1200, 900))
        self.actor_data = actor_data or {}
        self.actor_id = actor_data.get('id') if actor_data else None
        self.actor_names = []
        self.all_productions = []
        self.all_rehearsals = []
        self.all_actors = []
        
        # Данные о связях
        self.roles_data = []  # Список словарей: [{'role_id': X, 'production_id': Y, 'role_name': Z, 'production_title': W}, ...]
        self.rehearsal_ids = []  # Список ID репетиций
        self.production_ids = []  # Список ID постановок
        
        # Загружаем списки для выбора сначала
        self.load_all_data()
        
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        
        if self.actor_id:
            wx.CallLater(100, self.load_actor_connections)
    
    def load_all_data(self):
        """Загружает все данные для выбора"""
        # Загружаем постановки
        future_prods = run_async(db_manager.get_all_productions())
        if future_prods:
            try:
                self.all_productions = future_prods.result(timeout=10) or []
            except Exception as e:
                logging.error(f"Ошибка загрузки постановок: {e}")
        
        # Загружаем репетиции
        future_rehs = run_async(db_manager.get_all_rehearsals())
        if future_rehs:
            try:
                self.all_rehearsals = future_rehs.result(timeout=10) or []
            except Exception as e:
                logging.error(f"Ошибка загрузки репетиций: {e}")
    
    def load_actor_connections(self):
        """Загружает связи актера"""
        if not self.actor_id:
            return
        
        # Загружаем роли
        future_roles = run_async(db_manager.get_actor_roles(self.actor_id))
        if future_roles:
            try:
                roles_result = future_roles.result(timeout=10) or []
                self.roles_data = []
                for role in roles_result:
                    self.roles_data.append({
                        'role_id': role.get('role_id'),
                        'production_id': role.get('production_id'),
                        'role_name': role.get('role_name', ''),
                        'production_title': role.get('production_title', '')
                    })
                self.update_roles_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки ролей: {e}")
        
        # Загружаем репетиции
        future_rehs = run_async(db_manager.get_actor_rehearsals(self.actor_id))
        if future_rehs:
            try:
                rehearsals_result = future_rehs.result(timeout=10) or []
                self.rehearsal_ids = [r.get('rehearsal_id') for r in rehearsals_result]
                self.update_rehearsals_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки репетиций: {e}")
        
        # Загружаем постановки
        future_prods = run_async(db_manager.get_actor_productions(self.actor_id))
        if future_prods:
            try:
                productions_result = future_prods.result(timeout=10) or []
                self.production_ids = [p.get('production_id') for p in productions_result]
                self.update_productions_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки постановок: {e}")
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Основные данные
        main_data_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        label = wx.StaticText(panel, -1, "ФИО актера:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        left_sizer.Add(label, 0, wx.ALL, 5)
        
        def validate_full_name_field(v):
            """Валидация ФИО для актера"""
            is_valid, error_msg = validate_full_name(v)
            if not is_valid and error_msg:
                return False
            return is_valid
        
        self.full_name = ValidatedTextCtrl(panel, 
                                          validator_func=validate_full_name_field,
                                          error_message="ФИО должно быть от 3 до 255 символов и содержать только буквы, пробелы, дефисы и точки")
        self.full_name.SetHint("Введите ФИО актера (например: Иванов Иван Иванович)")
        left_sizer.Add(self.full_name, 0, wx.EXPAND | wx.ALL, 5)
        
        # Метка для ошибки
        error_label = wx.StaticText(panel, -1, "")
        error_label.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        left_sizer.Add(error_label, 0, wx.LEFT | wx.BOTTOM, 5)
        
        full_name_value = self.actor_data.get('full_name') or ''
        if full_name_value:
            def set_value():
                try:
                    self.full_name.SetValue(str(full_name_value))
                except Exception as e:
                    logging.debug(f"Ошибка установки значения: {e}")
            wx.CallLater(100, set_value)
        self.add_validated_field(self.full_name, validate_full_name_field, required=True, error_label=error_label)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Опыт и портфолио:"), 0, wx.ALL, 5)
        self.experience = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(-1, 150))
        experience_value = self.actor_data.get('experience') or ''
        self.experience.SetValue(str(experience_value) if experience_value else '')
        self.experience.SetHint("Опыт и портфолио актера (необязательно)")
        left_sizer.Add(self.experience, 1, wx.EXPAND | wx.ALL, 5)
        
        main_data_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Notebook для управления связями
        notebook = wx.Notebook(panel)
        
        # Вкладка: Роли
        roles_page = wx.Panel(notebook)
        roles_sizer = wx.BoxSizer(wx.VERTICAL)
        roles_sizer.Add(wx.StaticText(roles_page, -1, "🎭 Роли в постановках:"), 0, wx.ALL, 5)
        self.roles_listbox = wx.ListBox(roles_page, -1, style=wx.LB_SINGLE, size=(350, 200))
        roles_sizer.Add(self.roles_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        roles_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_role = wx.Button(roles_page, -1, "➕ Добавить роль")
        self.btn_add_role.Bind(wx.EVT_BUTTON, self.on_add_role)
        self.btn_remove_role = wx.Button(roles_page, -1, "❌ Удалить роль")
        self.btn_remove_role.Bind(wx.EVT_BUTTON, self.on_remove_role)
        roles_btn_sizer.Add(self.btn_add_role, 0, wx.RIGHT, 5)
        roles_btn_sizer.Add(self.btn_remove_role, 0)
        roles_sizer.Add(roles_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        roles_page.SetSizer(roles_sizer)
        notebook.AddPage(roles_page, "Роли")
        
        # Вкладка: Репетиции
        rehearsals_page = wx.Panel(notebook)
        rehearsals_sizer = wx.BoxSizer(wx.VERTICAL)
        rehearsals_sizer.Add(wx.StaticText(rehearsals_page, -1, "🎪 Репетиции:"), 0, wx.ALL, 5)
        self.rehearsals_listbox = wx.ListBox(rehearsals_page, -1, style=wx.LB_SINGLE, size=(350, 200))
        rehearsals_sizer.Add(self.rehearsals_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        rehearsals_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_rehearsal = wx.Button(rehearsals_page, -1, "➕ Добавить репетицию")
        self.btn_add_rehearsal.Bind(wx.EVT_BUTTON, self.on_add_rehearsal)
        self.btn_remove_rehearsal = wx.Button(rehearsals_page, -1, "❌ Удалить репетицию")
        self.btn_remove_rehearsal.Bind(wx.EVT_BUTTON, self.on_remove_rehearsal)
        rehearsals_btn_sizer.Add(self.btn_add_rehearsal, 0, wx.RIGHT, 5)
        rehearsals_btn_sizer.Add(self.btn_remove_rehearsal, 0)
        rehearsals_sizer.Add(rehearsals_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        rehearsals_page.SetSizer(rehearsals_sizer)
        notebook.AddPage(rehearsals_page, "Репетиции")
        
        # Вкладка: Постановки
        productions_page = wx.Panel(notebook)
        productions_sizer = wx.BoxSizer(wx.VERTICAL)
        productions_sizer.Add(wx.StaticText(productions_page, -1, "🎬 Постановки:"), 0, wx.ALL, 5)
        self.productions_listbox = wx.ListBox(productions_page, -1, style=wx.LB_SINGLE, size=(350, 200))
        productions_sizer.Add(self.productions_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        productions_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_production = wx.Button(productions_page, -1, "➕ Добавить постановку")
        self.btn_add_production.Bind(wx.EVT_BUTTON, self.on_add_production)
        self.btn_remove_production = wx.Button(productions_page, -1, "❌ Удалить постановку")
        self.btn_remove_production.Bind(wx.EVT_BUTTON, self.on_remove_production)
        productions_btn_sizer.Add(self.btn_add_production, 0, wx.RIGHT, 5)
        productions_btn_sizer.Add(self.btn_remove_production, 0)
        productions_sizer.Add(productions_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        productions_page.SetSizer(productions_sizer)
        notebook.AddPage(productions_page, "Постановки")
        
        main_data_sizer.Add(notebook, 1, wx.EXPAND | wx.LEFT, 5)
        sizer.Add(main_data_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        
        panel.SetSizer(sizer)
        self.validate_all()
    
    def update_roles_listbox(self):
        self.roles_listbox.Clear()
        items = []
        for role_data in self.roles_data:
            item = f"{role_data.get('role_name', '')} в '{role_data.get('production_title', '')}'"
            items.append(item)
        if items:
            self.roles_listbox.InsertItems(items, 0)
    
    def update_rehearsals_listbox(self):
        self.rehearsals_listbox.Clear()
        items = []
        for reh_id in self.rehearsal_ids:
            reh = next((r for r in self.all_rehearsals if r.get('id') == reh_id), None)
            if reh:
                dt = format_datetime_for_display(reh.get('datetime', ''))
                prod_title = reh.get('production_title', 'Без названия')
                items.append(f"{prod_title} - {dt}")
        if items:
            self.rehearsals_listbox.InsertItems(items, 0)
    
    def update_productions_listbox(self):
        self.productions_listbox.Clear()
        items = []
        for prod_id in self.production_ids:
            prod = next((p for p in self.all_productions if p.get('id') == prod_id), None)
            if prod:
                date_str = format_date_for_display(prod.get('production_date', ''))
                items.append(f"{prod.get('title', '')} ({date_str})")
        if items:
            self.productions_listbox.InsertItems(items, 0)
    
    def on_add_role(self, event):
        """Добавление роли актеру"""
        if not self.all_productions:
            show_error("Нет доступных постановок.")
            return
        
        dialog = wx.Dialog(self, title="Назначить роль", size=(700, 550))
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "Выберите постановку:*"), 0, wx.ALL, 5)
        prod_choices = [f"{p['title']} (ID: {p['id']})" for p in self.all_productions]
        prod_choice = wx.Choice(panel, -1, choices=prod_choices)
        sizer.Add(prod_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Выберите роль:*"), 0, wx.ALL, 5)
        role_choice = wx.Choice(panel, -1, choices=[])
        sizer.Add(role_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        def on_prod_changed(e):
            sel = prod_choice.GetSelection()
            if sel != wx.NOT_FOUND:
                prod = self.all_productions[sel]
                future_roles = run_async(db_manager.get_roles_for_play(prod['play_id']))
                roles = []
                if future_roles:
                    try:
                        roles = future_roles.result(timeout=5) or []
                    except Exception: pass
                role_choice.SetItems([f"{r['title']} (ID: {r['id']})" for r in roles])
        
        prod_choice.Bind(wx.EVT_CHOICE, on_prod_changed)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        if dialog.ShowModal() == wx.ID_OK:
            prod_sel = prod_choice.GetSelection()
            role_sel = role_choice.GetSelection()
            if prod_sel != wx.NOT_FOUND and role_sel != wx.NOT_FOUND:
                prod = self.all_productions[prod_sel]
                future_roles = run_async(db_manager.get_roles_for_play(prod['play_id']))
                roles = []
                if future_roles:
                    try:
                        roles = future_roles.result(timeout=5) or []
                    except Exception: pass
                if role_sel < len(roles):
                    role = roles[role_sel]
                    # Проверяем, нет ли уже такой роли
                    existing = next((r for r in self.roles_data if r['role_id'] == role['id'] and r['production_id'] == prod['id']), None)
                    if existing:
                        show_error("Эта роль уже назначена в данной постановке.")
                    else:
                        self.roles_data.append({
                            'role_id': role['id'],
                            'production_id': prod['id'],
                            'role_name': role['title'],
                            'production_title': prod['title']
                        })
                        self.update_roles_listbox()
        
        dialog.Destroy()
    
    def on_remove_role(self, event):
        sel = self.roles_listbox.GetSelection()
        if sel == wx.NOT_FOUND:
            show_error("Выберите роль для удаления.")
            return
        
        if sel < len(self.roles_data):
            del self.roles_data[sel]
            self.update_roles_listbox()
    
    def on_add_rehearsal(self, event):
        """Добавление репетиции"""
        available_rehs = [r for r in self.all_rehearsals if r.get('id') not in self.rehearsal_ids]
        if not available_rehs:
            show_error("Все репетиции уже добавлены.")
            return
        
        dialog = wx.Dialog(self, title="Добавить репетицию", size=(700, 500))
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "Выберите репетицию:*"), 0, wx.ALL, 5)
        reh_choices = []
        for r in available_rehs:
            dt = format_datetime_for_display(r.get('datetime', ''))
            prod_title = r.get('production_title', 'Без названия')
            reh_choices.append(f"{prod_title} - {dt} (ID: {r.get('id', '?')})")
        reh_choice = wx.Choice(panel, -1, choices=reh_choices)
        sizer.Add(reh_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        if dialog.ShowModal() == wx.ID_OK:
            sel = reh_choice.GetSelection()
            if sel != wx.NOT_FOUND and sel < len(available_rehs):
                reh = available_rehs[sel]
                if reh.get('id') not in self.rehearsal_ids:
                    self.rehearsal_ids.append(reh.get('id'))
                    self.update_rehearsals_listbox()
        
        dialog.Destroy()
    
    def on_remove_rehearsal(self, event):
        sel = self.rehearsals_listbox.GetSelection()
        if sel == wx.NOT_FOUND:
            show_error("Выберите репетицию для удаления.")
            return
        
        if sel < len(self.rehearsal_ids):
            del self.rehearsal_ids[sel]
            self.update_rehearsals_listbox()
    
    def on_add_production(self, event):
        """Добавление постановки"""
        available_prods = [p for p in self.all_productions if p.get('id') not in self.production_ids]
        if not available_prods:
            show_error("Все постановки уже добавлены.")
            return
        
        dialog = wx.Dialog(self, title="Добавить постановку", size=(700, 500))
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "Выберите постановку:*"), 0, wx.ALL, 5)
        prod_choices = [f"{p['title']} (ID: {p['id']})" for p in available_prods]
        prod_choice = wx.Choice(panel, -1, choices=prod_choices)
        sizer.Add(prod_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        if dialog.ShowModal() == wx.ID_OK:
            sel = prod_choice.GetSelection()
            if sel != wx.NOT_FOUND and sel < len(available_prods):
                prod = available_prods[sel]
                if prod.get('id') not in self.production_ids:
                    self.production_ids.append(prod.get('id'))
                    self.update_productions_listbox()
        
        dialog.Destroy()
    
    def on_remove_production(self, event):
        sel = self.productions_listbox.GetSelection()
        if sel == wx.NOT_FOUND:
            show_error("Выберите постановку для удаления.")
            return
        
        if sel < len(self.production_ids):
            # Удаляем также роли из этой постановки
            prod_id = self.production_ids[sel]
            self.roles_data = [r for r in self.roles_data if r['production_id'] != prod_id]
            del self.production_ids[sel]
            self.update_productions_listbox()
            self.update_roles_listbox()
        
    def get_data(self):
        experience_value = self.experience.GetValue().strip()
        return {
            'full_name': self.full_name.GetValue().strip(),
            'experience': experience_value if experience_value else None,
            'roles_data': self.roles_data.copy(),
            'rehearsal_ids': self.rehearsal_ids.copy(),
            'production_ids': self.production_ids.copy()
        }

class ViewActorDialog(wx.Dialog):
    def __init__(self, parent, title, actor_data):
        super().__init__(parent, title=title, size=(900, 800), 
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.actor_data = actor_data
        self.actor_id = actor_data.get('id')
        self.roles_data = []
        self.rehearsals_data = []
        self.productions_data = []
        self.init_ui()
        self.load_actor_connections()
        
    def on_size(self, event):
        # Обработчик изменения размера окна
        event.Skip()
        self.Layout()
    
    def load_actor_connections(self):
        # Загружаем все связи актера
        if not self.actor_id:
            return
        
        # Загружаем роли
        future_roles = run_async(db_manager.get_actor_roles(self.actor_id))
        if future_roles:
            try:
                self.roles_data = future_roles.result(timeout=10) or []
                self.update_roles_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки ролей актера: {e}")
        
        # Загружаем репетиции
        future_rehearsals = run_async(db_manager.get_actor_rehearsals(self.actor_id))
        if future_rehearsals:
            try:
                self.rehearsals_data = future_rehearsals.result(timeout=10) or []
                self.update_rehearsals_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки репетиций актера: {e}")
        
        # Загружаем постановки
        future_productions = run_async(db_manager.get_actor_productions(self.actor_id))
        if future_productions:
            try:
                self.productions_data = future_productions.result(timeout=10) or []
                self.update_productions_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки постановок актера: {e}")
        
    def init_ui(self):
        scroll = wx.ScrolledWindow(self)
        scroll.SetScrollRate(10, 10)
        panel = wx.Panel(scroll)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "👤 Просмотр актера")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        # Основная информация
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_info = wx.BoxSizer(wx.VERTICAL)
        
        left_info.Add(wx.StaticText(panel, -1, "ФИО актера:"), 0, wx.ALL, 5)
        self.full_name = wx.TextCtrl(panel, -1, self.actor_data.get('full_name', ''), style=wx.TE_READONLY)
        left_info.Add(self.full_name, 0, wx.EXPAND | wx.ALL, 5)
        
        left_info.Add(wx.StaticText(panel, -1, "Опыт и портфолио:"), 0, wx.ALL, 5)
        self.experience = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 150))
        self.experience.SetValue(self.actor_data.get('experience', ''))
        left_info.Add(self.experience, 1, wx.EXPAND | wx.ALL, 5)
        
        info_sizer.Add(left_info, 1, wx.EXPAND)
        sizer.Add(info_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Notebook для вкладок со связями
        notebook = wx.Notebook(panel)
        
        # Вкладка: Роли в постановках
        roles_page = wx.Panel(notebook)
        roles_sizer = wx.BoxSizer(wx.VERTICAL)
        roles_sizer.Add(wx.StaticText(roles_page, -1, "🎭 Роли в постановках:"), 0, wx.ALL, 5)
        self.roles_listbox = wx.ListBox(roles_page, -1, style=wx.LB_SINGLE, size=(-1, 200))
        roles_sizer.Add(self.roles_listbox, 1, wx.EXPAND | wx.ALL, 5)
        roles_page.SetSizer(roles_sizer)
        notebook.AddPage(roles_page, "Роли")
        
        # Вкладка: Репетиции
        rehearsals_page = wx.Panel(notebook)
        rehearsals_sizer = wx.BoxSizer(wx.VERTICAL)
        rehearsals_sizer.Add(wx.StaticText(rehearsals_page, -1, "🎪 Репетиции:"), 0, wx.ALL, 5)
        self.rehearsals_listbox = wx.ListBox(rehearsals_page, -1, style=wx.LB_SINGLE, size=(-1, 200))
        rehearsals_sizer.Add(self.rehearsals_listbox, 1, wx.EXPAND | wx.ALL, 5)
        rehearsals_page.SetSizer(rehearsals_sizer)
        notebook.AddPage(rehearsals_page, "Репетиции")
        
        # Вкладка: Постановки
        productions_page = wx.Panel(notebook)
        productions_sizer = wx.BoxSizer(wx.VERTICAL)
        productions_sizer.Add(wx.StaticText(productions_page, -1, "🎬 Постановки:"), 0, wx.ALL, 5)
        self.productions_listbox = wx.ListBox(productions_page, -1, style=wx.LB_SINGLE, size=(-1, 200))
        productions_sizer.Add(self.productions_listbox, 1, wx.EXPAND | wx.ALL, 5)
        productions_page.SetSizer(productions_sizer)
        notebook.AddPage(productions_page, "Постановки")
        
        sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        scroll_sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 5)
        scroll.SetSizer(scroll_sizer)
        scroll.SetAutoLayout(True)
        scroll.FitInside()
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(scroll, 1, wx.EXPAND)
        self.SetSizer(main_sizer)
        self.Bind(wx.EVT_SIZE, self.on_size)
    
    def update_roles_listbox(self):
        self.roles_listbox.Clear()
        items = []
        for role_data in self.roles_data:
            prod_date = role_data.get('production_date', '')
            date_str = format_date_for_display(prod_date) if prod_date else 'Без даты'
            item = f"{role_data.get('role_name', '')} в '{role_data.get('production_title', '')}' ({date_str})"
            items.append(item)
        if items:
            self.roles_listbox.InsertItems(items, 0)
    
    def update_rehearsals_listbox(self):
        self.rehearsals_listbox.Clear()
        items = []
        for reh_data in self.rehearsals_data:
            dt = reh_data.get('datetime', '')
            dt_str = format_datetime_for_display(dt) if dt else 'Без даты'
            item = f"{reh_data.get('production_title', '')} - {dt_str} ({reh_data.get('theatre_name', '')})"
            items.append(item)
        if items:
            self.rehearsals_listbox.InsertItems(items, 0)
    
    def update_productions_listbox(self):
        self.productions_listbox.Clear()
        items = []
        for prod_data in self.productions_data:
            prod_date = prod_data.get('production_date', '')
            date_str = format_date_for_display(prod_date) if prod_date else 'Без даты'
            item = f"{prod_data.get('title', '')} ({prod_data.get('play_title', '')}) - {date_str}"
            items.append(item)
        if items:
            self.productions_listbox.InsertItems(items, 0)
    

class EditAuthorDialog(ValidatedDialog):
    def __init__(self, parent, title, author_data=None):
        super().__init__(parent, title, size=(800, 600))
        self.author_data = author_data or {}
        self.author_id = author_data.get('id') if author_data else None
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
    
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "ФИО автора:*"), 0, wx.ALL, 5)
        
        def validate_full_name_field(v):
            is_valid, error_msg = validate_full_name(v)
            if not is_valid and error_msg:
                return False
            return is_valid
        
        self.full_name = ValidatedTextCtrl(panel, 
                                          validator_func=validate_full_name_field,
                                          error_message="ФИО должно быть от 3 до 255 символов и содержать только буквы, пробелы, дефисы и точки")
        self.full_name.SetHint("Введите ФИО автора (например: Чехов Антон Павлович)")
        sizer.Add(self.full_name, 0, wx.EXPAND | wx.ALL, 5)
        full_name_value = self.author_data.get('full_name') or ''
        if full_name_value:
            def set_value():
                try:
                    self.full_name.SetValue(str(full_name_value))
                except Exception as e:
                    logging.debug(f"Ошибка установки значения: {e}")
            wx.CallLater(100, set_value)
        self.add_validated_field(self.full_name, validate_full_name_field)
        
        sizer.Add(wx.StaticText(panel, -1, "Биография:"), 0, wx.ALL, 5)
        self.biography = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(-1, 200))
        biography_value = self.author_data.get('biography') or ''
        self.biography.SetValue(str(biography_value) if biography_value else '')
        self.biography.SetHint("Биография автора (необязательно)")
        sizer.Add(self.biography, 1, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        panel.SetSizer(sizer)
        self.validate_all()
        
    def get_data(self):
        biography_value = self.biography.GetValue().strip()
        return {
            'full_name': self.full_name.GetValue().strip(),
            'biography': biography_value if biography_value else None
        }

class SettingsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Настройки", size=(600, 500))
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
    
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "Тема интерфейса:"), 0, wx.ALL, 10)
        
        self.theme_choice = wx.RadioBox(panel, -1, "", choices=["Светлая", "Темная"], 
                                         majorDimension=2, style=wx.RA_SPECIFY_COLS)
        current_theme = theme_manager.get_current_theme_name()
        self.theme_choice.SetSelection(0 if current_theme == 'light' else 1)
        sizer.Add(self.theme_choice, 0, wx.EXPAND | wx.ALL, 10)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        self.Bind(wx.EVT_BUTTON, self.on_ok, ok_btn)
    
    def on_ok(self, event):
        theme_index = self.theme_choice.GetSelection()
        theme_name = 'light' if theme_index == 0 else 'dark'
        theme_manager.set_theme(theme_name, manual=True)
        theme_manager.apply_theme_to_all_windows()
        
        def refresh_dashboard():
            parent = self.GetParent()
            if isinstance(parent, DashboardPanel) and hasattr(parent, 'refresh_charts'):
                parent.refresh_charts()
            else:
                for window in wx.GetTopLevelWindows():
                    if isinstance(window, wx.Frame):
                        for child in window.GetChildren():
                            if isinstance(child, DashboardPanel) and hasattr(child, 'refresh_charts'):
                                child.refresh_charts()
                                return
        
        wx.CallAfter(refresh_dashboard)
        event.Skip()

class ViewAuthorDialog(wx.Dialog):
    def __init__(self, parent, title, author_data):
        super().__init__(parent, title=title, size=(800, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.author_data = author_data
        self.author_id = author_data.get('id')
        self.plays_data = []
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        if self.author_id:
            self.load_plays()
        
    def load_plays(self):
        """Загружает пьесы автора"""
        if not self.author_id:
            return
        
        future = run_async(db_manager.get_plays_for_author(self.author_id))
        if future:
            try:
                self.plays_data = future.result(timeout=10) or []
                self.update_plays_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки пьес: {e}")
    
    def update_plays_listbox(self):
        """Обновляет список пьес"""
        if not hasattr(self, 'plays_listbox'):
            return
        
        self.plays_listbox.Clear()
        items = []
        for play in self.plays_data:
            title = play.get('title', 'Неизвестно')
            genre = play.get('genre', '')
            items.append(f"{title} ({genre})" if genre else title)
        
        if items:
            self.plays_listbox.InsertItems(items, 0)
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "✍️ Просмотр автора")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        # Основная информация
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        left_sizer.Add(wx.StaticText(panel, -1, "ФИО автора:"), 0, wx.ALL, 5)
        full_name_value = self.author_data.get('full_name') or ''
        self.full_name = wx.TextCtrl(panel, -1, str(full_name_value) if full_name_value else '', style=wx.TE_READONLY)
        left_sizer.Add(self.full_name, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Биография:"), 0, wx.ALL, 5)
        self.biography = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 200))
        biography_value = self.author_data.get('biography') or ''
        self.biography.SetValue(str(biography_value) if biography_value else '')
        left_sizer.Add(self.biography, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Пьесы
        plays_sizer = wx.BoxSizer(wx.VERTICAL)
        plays_sizer.Add(wx.StaticText(panel, -1, "📜 Пьесы автора:"), 0, wx.ALL, 5)
        self.plays_listbox = wx.ListBox(panel, -1, style=wx.LB_SINGLE, size=(300, 250))
        plays_sizer.Add(self.plays_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(plays_sizer, 1, wx.EXPAND | wx.LEFT, 5)
        sizer.Add(main_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        self.SetMinSize((900, 700))

class EditDirectorDialog(ValidatedDialog):
    def __init__(self, parent, title, director_data=None):
        super().__init__(parent, title, size=(900, 750))
        self.director_data = director_data or {}
        self.director_names = []
        self.init_ui()
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "ФИО режиссера:*"), 0, wx.ALL, 5)
        
        def validate_full_name_field(v):
            """Валидация ФИО для режиссера"""
            is_valid, error_msg = validate_full_name(v)
            if not is_valid and error_msg:
                return False
            return is_valid
        
        self.full_name = ValidatedTextCtrl(panel, 
                                          validator_func=validate_full_name_field,
                                          error_message="ФИО должно быть от 3 до 255 символов и содержать только буквы, пробелы, дефисы и точки")
        self.full_name.SetHint("Введите ФИО режиссера (например: Станиславский Константин Сергеевич)")
        sizer.Add(self.full_name, 0, wx.EXPAND | wx.ALL, 5)
        full_name_value = self.director_data.get('full_name') or ''
        if full_name_value:
            def set_value():
                try:
                    self.full_name.SetValue(str(full_name_value))
                except Exception as e:
                    logging.debug(f"Ошибка установки значения: {e}")
            wx.CallLater(100, set_value)
        self.add_validated_field(self.full_name, validate_full_name_field)
        
        sizer.Add(wx.StaticText(panel, -1, "Биография:"), 0, wx.ALL, 5)
        self.biography = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(-1, 400))
        biography_value = self.director_data.get('biography') or ''
        self.biography.SetValue(str(biography_value) if biography_value else '')
        self.biography.SetHint("Биография режиссера (необязательно)")
        sizer.Add(self.biography, 1, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        
        panel.SetSizer(sizer)
        # Убираем ограничение минимального размера для лучшей адаптивности
        self.validate_all()
        
    def get_data(self):
        biography_value = self.biography.GetValue().strip()
        return {
            'full_name': self.full_name.GetValue().strip(),
            'biography': biography_value if biography_value else None
        }

class ViewDirectorDialog(wx.Dialog):
    def __init__(self, parent, title, director_data):
        super().__init__(parent, title=title, size=(700, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.director_data = director_data
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "🎬 Просмотр режиссера")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        sizer.Add(wx.StaticText(panel, -1, "ФИО режиссера:"), 0, wx.ALL, 5)
        self.full_name = wx.TextCtrl(panel, -1, self.director_data.get('full_name', ''), style=wx.TE_READONLY)
        sizer.Add(self.full_name, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Биография:"), 0, wx.ALL, 5)
        self.biography = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 400))
        self.biography.SetValue(self.director_data.get('biography', ''))
        sizer.Add(self.biography, 1, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        # Убираем ограничение минимального размера для лучшей адаптивности

class EditPlayDialog(ValidatedDialog):
    def __init__(self, parent, title, play_data=None):
        super().__init__(parent, title, size=(1100, 900))
        self.play_data = play_data or {}
        self.genres = []
        self.all_authors = []
        self.play_author_ids = set() # ID авторов этой пьесы
        self.init_ui()

        self.load_all_authors_and_selection()

    def load_all_authors_and_selection(self):
        # Загружаем всех авторов
        future_all = run_async(db_manager.get_all_authors())
        if future_all:
            try:
                self.all_authors = future_all.result(timeout=10) or []
            except Exception as e:
                logging.error(f"Не удалось загрузить авторов: {e}")

        # Если это редактирование, загружаем текущих авторов пьесы
        play_id = self.play_data.get('id')
        if play_id:
            future_selected = run_async(db_manager.get_authors_for_play(play_id))
            if future_selected:
                try:
                    selected_authors = future_selected.result(timeout=10) or []
                    self.play_author_ids = {author['id'] for author in selected_authors}
                except Exception as e:
                    logging.error(f"Не удалось загрузить авторов пьесы: {e}")

        self.update_author_listbox()

    def update_author_listbox(self):
        if not hasattr(self, 'author_listbox'):
            return

        self.author_listbox.Clear()
        items = []
        selected_indices = []
        for i, author in enumerate(self.all_authors):
            items.append(f"{author['full_name']} (ID: {author['id']})")
            if author['id'] in self.play_author_ids:
                selected_indices.append(i)

        if items:
            self.author_listbox.InsertItems(items, 0)
            for idx in selected_indices:
                self.author_listbox.Check(idx)

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        left_sizer = wx.BoxSizer(wx.VERTICAL)

        left_sizer.Add(wx.StaticText(panel, -1, "Название пьесы:*"), 0, wx.ALL, 5)
        self.title = wx.TextCtrl(panel, -1, self.play_data.get('title', ''))
        left_sizer.Add(self.title, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.title, lambda v: len(v.strip()) > 0, required=True)

        left_sizer.Add(wx.StaticText(panel, -1, "Жанр:"), 0, wx.ALL, 5)
        future = run_async(db_manager.get_unique_genres())
        if future:
            try:
                self.genres = future.result(timeout=5) or []
            except: pass

        self.genre = ComboTextCtrl(panel, choices=self.genres)
        self.genre.SetValue(self.play_data.get('genre', ''))
        left_sizer.Add(self.genre, 0, wx.EXPAND | wx.ALL, 5)

        left_sizer.Add(wx.StaticText(panel, -1, "Год написания:"), 0, wx.ALL, 5)
        year_value = self.play_data.get('year_written')
        self.year_written = ValidatedTextCtrl(panel, 
                                            validator_func=lambda v: (not v.strip() or (v.strip().isdigit() and len(v.strip()) == 4 and 1000 <= int(v.strip()) <= 2100)),
                                            error_message="Год должен быть 4-значным числом")
        self.year_written.SetValue(str(year_value) if year_value else '')
        left_sizer.Add(self.year_written, 0, wx.EXPAND | wx.ALL, 5)

        left_sizer.Add(wx.StaticText(panel, -1, "Описание:"), 0, wx.ALL, 5)
        self.description = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(-1, 150))
        self.description.SetValue(self.play_data.get('description', ''))
        left_sizer.Add(self.description, 1, wx.EXPAND | wx.ALL, 5)

        main_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 5)

        # --- Список Авторов ---
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_sizer.Add(wx.StaticText(panel, -1, "Авторы (можно выбрать нескольких):*"), 0, wx.ALL, 5)
        self.author_listbox = wx.CheckListBox(panel, -1, size=(350, 300))
        right_sizer.Add(self.author_listbox, 1, wx.EXPAND | wx.ALL, 5)

        # Валидация, что хотя бы один автор выбран
        def validate_authors(v):
            return len(self.author_listbox.GetCheckedItems()) > 0
        self.add_validated_field(self.author_listbox, validate_authors, required=True)

        main_sizer.Add(right_sizer, 1, wx.EXPAND | wx.LEFT, 5)
        sizer.Add(main_sizer, 1, wx.EXPAND | wx.ALL, 5)

        # --- Кнопки OK/Cancel ---
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.set_ok_button(ok_btn)
        panel.SetSizer(sizer)
        self.validate_all()

    def get_data(self):
        year_str = self.year_written.GetValue().strip()
        year = int(year_str) if year_str and year_str.isdigit() else None

        play_data = {
            'title': self.title.GetValue().strip(),
            'genre': self.genre.get_value(),
            'year_written': year,
            'description': self.description.GetValue().strip() or None
        }

        # Собираем ID выбранных авторов
        selected_author_ids = []
        checked_indices = self.author_listbox.GetCheckedItems()
        for idx in checked_indices:
            if idx < len(self.all_authors):
                selected_author_ids.append(self.all_authors[idx]['id'])

        return play_data, selected_author_ids

class ViewPlayDialog(wx.Dialog):
    def __init__(self, parent, title, play_data):
        super().__init__(parent, title=title, size=(800, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.play_data = play_data
        self.play_id = play_data.get('id')
        self.authors_data = []
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        if self.play_id:
            self.load_authors()
        
    def load_authors(self):
        """Загружает авторов пьесы"""
        if not self.play_id:
            return
        
        future = run_async(db_manager.get_authors_for_play(self.play_id))
        if future:
            try:
                self.authors_data = future.result(timeout=10) or []
                self.update_authors_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки авторов: {e}")
    
    def update_authors_listbox(self):
        """Обновляет список авторов"""
        if not hasattr(self, 'authors_listbox'):
            return
        
        self.authors_listbox.Clear()
        items = []
        for author in self.authors_data:
            author_name = author.get('full_name', 'Неизвестно')
            items.append(author_name)
        
        if items:
            self.authors_listbox.InsertItems(items, 0)
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "📜 Просмотр пьесы")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        # Основная информация
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Название пьесы:"), 0, wx.ALL, 5)
        self.title = wx.TextCtrl(panel, -1, self.play_data.get('title', ''), style=wx.TE_READONLY)
        left_sizer.Add(self.title, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Жанр:"), 0, wx.ALL, 5)
        self.genre = wx.TextCtrl(panel, -1, self.play_data.get('genre', ''), style=wx.TE_READONLY)
        left_sizer.Add(self.genre, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Год написания:"), 0, wx.ALL, 5)
        self.year_written = wx.TextCtrl(panel, -1, str(self.play_data.get('year_written', '')), style=wx.TE_READONLY)
        left_sizer.Add(self.year_written, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Описание:"), 0, wx.ALL, 5)
        self.description = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 200))
        self.description.SetValue(self.play_data.get('description', ''))
        left_sizer.Add(self.description, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Авторы
        authors_sizer = wx.BoxSizer(wx.VERTICAL)
        authors_sizer.Add(wx.StaticText(panel, -1, "✍️ Авторы пьесы:"), 0, wx.ALL, 5)
        self.authors_listbox = wx.ListBox(panel, -1, style=wx.LB_SINGLE, size=(300, 250))
        authors_sizer.Add(self.authors_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(authors_sizer, 1, wx.EXPAND | wx.LEFT, 5)
        sizer.Add(main_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        self.SetMinSize((900, 700))

class AssignRoleDialog(ValidatedDialog):
    # Диалог для назначения актера на роль в постановке
    def __init__(self, parent, play_id, actors_list, existing_actor_ids):
        super().__init__(parent, "Назначить актера на роль", size=(700, 550))
        self.play_id = play_id
        self.actors = [actor for actor in actors_list if actor['id'] not in existing_actor_ids]
        self.roles = []
        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Выбор Актера
        sizer.Add(wx.StaticText(panel, -1, "Актер:*"), 0, wx.ALL, 5)
        actor_choices = [f"{actor['full_name']} (ID: {actor['id']})" for actor in self.actors]
        self.actor_choice = wx.Choice(panel, -1, choices=actor_choices)
        sizer.Add(self.actor_choice, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.actor_choice, lambda v: v != wx.NOT_FOUND, required=True)

        # Выбор Роли
        sizer.Add(wx.StaticText(panel, -1, "Роль:*"), 0, wx.ALL, 5)
        
        # Загружаем роли для пьесы
        future = run_async(db_manager.get_roles_for_play(self.play_id))
        role_choices = []
        if future:
            try:
                self.roles = future.result(timeout=5) or []
                role_choices = [f"{role['title']} (ID: {role['id']})" for role in self.roles]
            except Exception as e:
                logging.error(f"Не удалось загрузить роли: {e}")
        
        self.role_choice = wx.Choice(panel, -1, choices=role_choices)
        sizer.Add(self.role_choice, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.role_choice, lambda v: v != wx.NOT_FOUND, required=True)
        
        if not self.roles:
            sizer.Add(wx.StaticText(panel, -1, "Для этой пьесы роли не найдены.\nСначала добавьте роли в справочнике 'Роли'."), 0, wx.ALL, 5)
        if not self.actors:
             sizer.Add(wx.StaticText(panel, -1, "Все актеры уже добавлены в постановку."), 0, wx.ALL, 5)


        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.set_ok_button(ok_btn)
        panel.SetSizer(sizer)
        self.validate_all()

    def get_data(self):
        selected_actor_idx = self.actor_choice.GetSelection()
        selected_role_idx = self.role_choice.GetSelection()

        if selected_actor_idx == wx.NOT_FOUND or selected_role_idx == wx.NOT_FOUND:
            return None

        actor = self.actors[selected_actor_idx]
        role = self.roles[selected_role_idx]

        return {
            'actor_id': actor['id'],
            'actor_name': actor['full_name'],
            'role_id': role['id'],
            'role_name': role['title']
        }

class EditProductionDialog(ValidatedDialog):
    def __init__(self, parent, title, production_data=None):
        super().__init__(parent, title, size=(1200, 900))
        self.production_data = production_data or {}
        self.plays = []
        self.directors = []
        self.all_actors = []
        self.cast_data = {}  # Внутренний кэш состава: {actor_id: {'actor_name': X, 'role_id': Y, 'role_name': Z}}
        self.play_id_on_load = self.production_data.get('play_id')
        
        self.init_ui()
        
        # Если это редактирование, загружаем состав
        if self.play_id_on_load and self.production_data.get('id'):
            self.load_cast_data(self.production_data['id'])
        
        # Загружаем список всех актеров в фон
        self.load_all_actors()

    def load_all_actors(self):
        future = run_async(db_manager.get_all_actors())
        if future:
            try:
                self.all_actors = future.result(timeout=10) or []
            except Exception as e:
                logging.error(f"Не удалось загрузить список актеров: {e}")

    def load_cast_data(self, production_id):
        future = run_async(db_manager.get_cast_for_production(production_id))
        if future:
            try:
                cast_results = future.result(timeout=10) or []
                self.cast_data.clear()
                for item in cast_results:
                    self.cast_data[item['actor_id']] = {
                        'actor_name': item['actor_name'],
                        'role_id': item['role_id'],
                        'role_name': item['role_name']
                    }
                self.update_cast_listbox()
            except Exception as e:
                logging.error(f"Не удалось загрузить состав: {e}")

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)


        # --- Основные данные ---
        main_data_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Название
        label_title = wx.StaticText(panel, -1, "Название постановки:*")
        left_sizer.Add(label_title, 0, wx.ALL, 5)
        self.title = wx.TextCtrl(panel, -1, self.production_data.get('title', ''))
        self.title.SetHint("Введите название постановки")
        left_sizer.Add(self.title, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.title, lambda v: len(v.strip()) > 0, required=True)
        
        # Дата
        left_sizer.Add(wx.StaticText(panel, -1, "Дата постановки:"), 0, wx.ALL, 5)
        production_date = self.production_data.get('production_date')
        date_val = format_date_for_display(production_date)
        self.production_date = AutoCompleteDateCtrl(panel, -1, value=date_val)
        left_sizer.Add(self.production_date, 0, wx.EXPAND | wx.ALL, 5)
        
        # Пьеса
        label_play = wx.StaticText(panel, -1, "Пьеса:*")
        left_sizer.Add(label_play, 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_plays())
        play_choices = ['']
        if future:
            try:
                self.plays = future.result(timeout=10) or []
                play_choices.extend([play['title'] for play in self.plays])
            except Exception: pass
            
        self.play_choice = wx.Choice(panel, -1, choices=play_choices)
        if self.play_id_on_load:
            play_idx = next((i+1 for i, play in enumerate(self.plays) if play['id'] == self.play_id_on_load), 0)
            self.play_choice.SetSelection(play_idx)
            
        left_sizer.Add(self.play_choice, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.play_choice, lambda v: v > 0, required=True)
        # Блокируем смену пьесы, если состав уже набран (чтобы избежать рассинхронизации ролей)
        if self.play_id_on_load:
            self.play_choice.Enable(False)
            left_sizer.Add(wx.StaticText(panel, -1, "Пьесу нельзя изменить, т.к. для нее уже набран состав."), 0, wx.LEFT, 5)
        else:
             # Если пьеса не выбрана, блокируем управление составом
            left_sizer.Add(wx.StaticText(panel, -1, "Сначала выберите пьесу, чтобы добавить актеров."), 0, wx.LEFT, 5)
            # Привязываем обработчик изменения пьесы для активации кнопок
            self.play_choice.Bind(wx.EVT_CHOICE, self.on_play_changed)
        
        # Режиссер
        label_director = wx.StaticText(panel, -1, "Режиссер:*")
        left_sizer.Add(label_director, 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_directors())
        director_choices = ['']
        if future:
            try:
                self.directors = future.result(timeout=10) or []
                director_choices.extend([director['full_name'] for director in self.directors])
            except Exception: pass
            
        self.director_choice = wx.Choice(panel, -1, choices=director_choices)
        if self.production_data.get('director_id'):
            director_idx = next((i+1 for i, director in enumerate(self.directors) if director['id'] == self.production_data['director_id']), 0)
            self.director_choice.SetSelection(director_idx)
        left_sizer.Add(self.director_choice, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.director_choice, lambda v: v > 0, required=True)

        # Описание
        left_sizer.Add(wx.StaticText(panel, -1, "Описание:"), 0, wx.ALL, 5)
        self.description = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(-1, 100))
        self.description.SetValue(self.production_data.get('description', ''))
        left_sizer.Add(self.description, 1, wx.EXPAND | wx.ALL, 5)
        
        main_data_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 5)

        # --- Актерский состав ---
        cast_sizer = wx.BoxSizer(wx.VERTICAL)
        cast_sizer.Add(wx.StaticText(panel, -1, "Актерский состав (Актер -> Роль):"), 0, wx.ALL, 5)
        self.cast_listbox = wx.ListBox(panel, -1, style=wx.LB_SINGLE, size=(350, 300))
        cast_sizer.Add(self.cast_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        cast_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_actor_btn = wx.Button(panel, -1, "Добавить актера")
        self.edit_role_btn = wx.Button(panel, -1, "Изменить роль")
        self.remove_actor_btn = wx.Button(panel, -1, "Удалить актера")
        cast_btn_sizer.Add(self.add_actor_btn, 0, wx.RIGHT, 5)
        cast_btn_sizer.Add(self.edit_role_btn, 0, wx.RIGHT, 5)
        cast_btn_sizer.Add(self.remove_actor_btn, 0)
        cast_sizer.Add(cast_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.add_actor_btn.Bind(wx.EVT_BUTTON, self.on_add_actor)
        self.edit_role_btn.Bind(wx.EVT_BUTTON, self.on_edit_role)
        self.remove_actor_btn.Bind(wx.EVT_BUTTON, self.on_remove_actor)
        self.cast_listbox.Bind(wx.EVT_LISTBOX_DCLICK, self.on_edit_role)
        
        # Блокируем кнопки, если пьеса не выбрана
        if not self.play_id_on_load:
            self.add_actor_btn.Enable(False)
            self.edit_role_btn.Enable(False)
            self.remove_actor_btn.Enable(False)
            self.cast_listbox.Enable(False)

        main_data_sizer.Add(cast_sizer, 1, wx.EXPAND | wx.LEFT, 5)
        sizer.Add(main_data_sizer, 1, wx.EXPAND | wx.ALL, 5)

        # --- Кнопки OK/Cancel ---
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.set_ok_button(ok_btn)
        panel.SetSizer(sizer)
        self.validate_all()
        
    def on_play_changed(self, event):
        # Активируем/деактивируем кнопки управления составом при изменении пьесы
        selected_play_idx = self.play_choice.GetSelection()
        if selected_play_idx > 0:
            self.add_actor_btn.Enable(True)
            self.edit_role_btn.Enable(True)
            self.remove_actor_btn.Enable(True)
            self.cast_listbox.Enable(True)
        else:
            self.add_actor_btn.Enable(False)
            self.edit_role_btn.Enable(False)
            self.remove_actor_btn.Enable(False)
            self.cast_listbox.Enable(False)
        event.Skip()
    
    def on_add_actor(self, event):
        selected_play_idx = self.play_choice.GetSelection()
        if selected_play_idx <= 0: # 0 - это пустая строка
            show_error("Сначала необходимо выбрать пьесу.")
            return
            
        play_id = self.plays[selected_play_idx - 1]['id']
        existing_actor_ids = self.cast_data.keys()
        
        dialog = AssignRoleDialog(self, play_id, self.all_actors, existing_actor_ids)
        if dialog.ShowModal() == wx.ID_OK:
            data = dialog.get_data()
            if data:
                # Добавляем в кэш
                self.cast_data[data['actor_id']] = {
                    'actor_name': data['actor_name'],
                    'role_id': data['role_id'],
                    'role_name': data['role_name']
                }
                self.update_cast_listbox()
        dialog.Destroy()
        
    def on_edit_role(self, event):
        selected_idx = self.cast_listbox.GetSelection()
        if selected_idx == wx.NOT_FOUND:
            show_error("Выберите актера из списка для изменения роли.")
            return
        
        selected_string = self.cast_listbox.GetString(selected_idx)
        try:
            actor_id_str = selected_string.split('(ID: ')[1].split(')')[0]
            actor_id = int(actor_id_str)
            
            if actor_id not in self.cast_data:
                show_error("Актер не найден в составе.")
                return
            
            current_data = self.cast_data[actor_id]
            selected_play_idx = self.play_choice.GetSelection()
            if selected_play_idx <= 0:
                show_error("Сначала необходимо выбрать пьесу.")
                return
            
            play_id = self.plays[selected_play_idx - 1]['id']
            
            # Создаем диалог для выбора новой роли
            future = run_async(db_manager.get_roles_for_play(play_id))
            roles = []
            if future:
                try:
                    roles = future.result(timeout=5) or []
                except Exception as e:
                    logging.error(f"Не удалось загрузить роли: {e}")
            
            if not roles:
                show_error("Для этой пьесы роли не найдены.")
                return
            
            role_choices = [f"{role['title']} (ID: {role['id']})" for role in roles]
            
            dialog = wx.Dialog(self, title="Изменить роль", size=(600, 400))
            panel = wx.Panel(dialog)
            sizer = wx.BoxSizer(wx.VERTICAL)
            
            sizer.Add(wx.StaticText(panel, -1, f"Актер: {current_data['actor_name']}"), 0, wx.ALL, 10)
            sizer.Add(wx.StaticText(panel, -1, "Новая роль:*"), 0, wx.ALL, 5)
            
            role_choice = wx.Choice(panel, -1, choices=role_choices)
            current_role_idx = next((i for i, role in enumerate(roles) if role['id'] == current_data['role_id']), 0)
            role_choice.SetSelection(current_role_idx)
            sizer.Add(role_choice, 0, wx.EXPAND | wx.ALL, 5)
            
            btn_sizer = wx.StdDialogButtonSizer()
            ok_btn = wx.Button(panel, wx.ID_OK, "OK")
            cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
            btn_sizer.AddButton(ok_btn)
            btn_sizer.AddButton(cancel_btn)
            btn_sizer.Realize()
            sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
            
            panel.SetSizer(sizer)
            
            if dialog.ShowModal() == wx.ID_OK:
                selected_role_idx = role_choice.GetSelection()
                if selected_role_idx != wx.NOT_FOUND:
                    selected_role = roles[selected_role_idx]
                    self.cast_data[actor_id]['role_id'] = selected_role['id']
                    self.cast_data[actor_id]['role_name'] = selected_role['title']
                    self.update_cast_listbox()
            
            dialog.Destroy()
        except Exception as e:
            logging.error(f"Ошибка изменения роли: {e}")
            show_error("Ошибка при изменении роли.")
    
    def on_remove_actor(self, event):
        selected_idx = self.cast_listbox.GetSelection()
        if selected_idx == wx.NOT_FOUND:
            show_error("Выберите актера из списка для удаления.")
            return
            
        selected_string = self.cast_listbox.GetString(selected_idx)
        # Парсим ID актера из строки
        try:
            actor_id_str = selected_string.split('(ID: ')[1].split(')')[0]
            actor_id = int(actor_id_str)
            
            if actor_id in self.cast_data:
                del self.cast_data[actor_id]
                self.update_cast_listbox()
        except Exception as e:
            logging.error(f"Ошибка удаления актера из списка: {e}")
            show_error("Ошибка при удалении актера из списка.")

    def update_cast_listbox(self):
        self.cast_listbox.Clear()
        items = []
        for actor_id, data in self.cast_data.items():
            display_str = f"{data['actor_name']} (ID: {actor_id}) -> {data['role_name']}"
            items.append(display_str)
        
        if items:
            self.cast_listbox.InsertItems(items, 0)

    def get_data(self):
        # Собираем основные данные
        play_id = None
        play_selection = self.play_choice.GetSelection()
        if play_selection > 0:
            play_id = self.plays[play_selection - 1]['id']
        
        director_id = None
        director_selection = self.director_choice.GetSelection()
        if director_selection > 0:
            director_id = self.directors[director_selection - 1]['id']
        
        production_main_data = {
            'title': self.title.GetValue().strip(),
            'production_date': self.production_date.get_date_value(),
            'play_id': play_id,
            'director_id': director_id,
            'description': self.description.GetValue().strip() or None
        }
        
        # Собираем данные о составе
        # Преобразуем наш кэш {actor_id: data} в список {actor_id: X, role_id: Y}
        production_cast_data = [
            {'actor_id': actor_id, 'role_id': data['role_id']}
            for actor_id, data in self.cast_data.items()
        ]
        
        return production_main_data, production_cast_data

class ViewProductionDialog(wx.Dialog):
    def __init__(self, parent, title, production_data):
        super().__init__(parent, title=title, size=(800, 700),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.production_data = production_data
        self.production_id = production_data.get('id')
        self.cast_data = []
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        if self.production_id:
            self.load_cast()
        
    def load_cast(self):
        """Загружает состав постановки"""
        if not self.production_id:
            return
        
        future = run_async(db_manager.get_cast_for_production(self.production_id))
        if future:
            try:
                self.cast_data = future.result(timeout=10) or []
                self.update_cast_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки состава: {e}")
    
    def update_cast_listbox(self):
        """Обновляет список актеров с ролями"""
        if not hasattr(self, 'cast_listbox'):
            return
        
        self.cast_listbox.Clear()
        items = []
        for cast_item in self.cast_data:
            actor_name = cast_item.get('actor_name', 'Неизвестно')
            role_name = cast_item.get('role_name', 'Без роли')
            items.append(f"{actor_name} -> {role_name}")
        
        if items:
            self.cast_listbox.InsertItems(items, 0)
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "🎭 Просмотр постановки")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        # Основная информация
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Название постановки:"), 0, wx.ALL, 5)
        self.title = wx.TextCtrl(panel, -1, self.production_data.get('title', ''), style=wx.TE_READONLY)
        left_sizer.Add(self.title, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Дата постановки:"), 0, wx.ALL, 5)
        production_date = self.production_data.get('production_date', '')
        production_date_str = format_date_for_display(production_date)
        self.production_date = wx.TextCtrl(panel, -1, production_date_str, style=wx.TE_READONLY)
        left_sizer.Add(self.production_date, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Пьеса:"), 0, wx.ALL, 5)
        play_id = self.production_data.get('play_id', 1)
        future = run_async(db_manager.get_all_plays())
        plays = future.result(timeout=10) if future else []
        play_title = next((play['title'] for play in plays if play['id'] == play_id), "Неизвестно")
        self.play = wx.TextCtrl(panel, -1, play_title, style=wx.TE_READONLY)
        left_sizer.Add(self.play, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Режиссер:"), 0, wx.ALL, 5)
        director_id = self.production_data.get('director_id', 1)
        future = run_async(db_manager.get_all_directors())
        directors = future.result(timeout=10) if future else []
        director_name = next((director['full_name'] for director in directors if director['id'] == director_id), "Неизвестно")
        self.director = wx.TextCtrl(panel, -1, director_name, style=wx.TE_READONLY)
        left_sizer.Add(self.director, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Описание:"), 0, wx.ALL, 5)
        self.description = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 150))
        self.description.SetValue(self.production_data.get('description', ''))
        left_sizer.Add(self.description, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Актерский состав
        cast_sizer = wx.BoxSizer(wx.VERTICAL)
        cast_sizer.Add(wx.StaticText(panel, -1, "🎬 Актерский состав:"), 0, wx.ALL, 5)
        self.cast_listbox = wx.ListBox(panel, -1, style=wx.LB_SINGLE, size=(300, 300))
        cast_sizer.Add(self.cast_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(cast_sizer, 1, wx.EXPAND | wx.LEFT, 5)
        sizer.Add(main_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        self.SetMinSize((900, 750))

class EditPerformanceDialog(ValidatedDialog):
    def __init__(self, parent, title, performance_data=None):
        super().__init__(parent, title, size=(1000, 800))
        self.performance_data = performance_data or {}
        self.productions = []
        self.locations = []
        self.init_ui()
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        
        label = wx.StaticText(panel, -1, "Постановка:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_productions())
        if future:
            try:
                self.productions = future.result(timeout=10) or []
                production_choices = [''] + [production['title'] for production in self.productions]
                self.production_choice = wx.Choice(panel, -1, choices=production_choices)
                if self.performance_data.get('production_id'):
                    prod_idx = next((i+1 for i, prod in enumerate(self.productions) if prod['id'] == self.performance_data['production_id']), 0)
                    self.production_choice.SetSelection(prod_idx)
                else:
                    self.production_choice.SetSelection(0)
                sizer.Add(self.production_choice, 0, wx.EXPAND | wx.ALL, 5)
            except Exception as e:
                logging.error(f"Ошибка загрузки постановок: {e}")
                self.production_choice = wx.Choice(panel, -1, choices=[''])
                sizer.Add(self.production_choice, 0, wx.EXPAND | wx.ALL, 5)
        else:
            self.production_choice = wx.Choice(panel, -1, choices=[''])
            sizer.Add(self.production_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_production = wx.StaticText(panel, -1, "")
        error_label_production.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_production.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_production, 0, wx.LEFT | wx.BOTTOM, 5)
        
        def validate_production(selection):
            return selection > 0  # Первый элемент - пустой
        
        self.add_validated_field(self.production_choice, validate_production, required=True, error_label=error_label_production)
        
        label = wx.StaticText(panel, -1, "Дата и время:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        datetime_val = self.performance_data.get('datetime', '')
        # Преобразуем в формат YYYY-MM-DD HH:MM:SS
        if hasattr(datetime_val, 'strftime'):
            datetime_val = datetime_val.strftime('%Y-%m-%d %H:%M:%S')
        elif datetime_val:
            # Если это строка, пробуем распарсить
            try:
                # Пробуем разные форматы
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y%m%d%H%M%S']:
                    try:
                        dt = datetime.strptime(str(datetime_val), fmt)
                        datetime_val = dt.strftime('%Y-%m-%d %H:%M:%S')
                        break
                    except:
                        continue
            except:
                pass
        self.datetime = AutoCompleteDateTimeCtrl(panel, -1, value=str(datetime_val) if datetime_val else '')
        self.datetime.SetHint("YYYY-MM-DD HH:MM:SS (введите цифры, разделители добавятся автоматически)")
        sizer.Add(self.datetime, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_datetime = wx.StaticText(panel, -1, "")
        error_label_datetime.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_datetime.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_datetime, 0, wx.LEFT | wx.BOTTOM, 5)
        
        label = wx.StaticText(panel, -1, "Место проведения:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_locations())
        if future:
            try:
                self.locations = future.result(timeout=10) or []
                location_choices = []
                for loc in self.locations:
                    address_parts = []
                    if loc.get('city'):
                        address_parts.append(loc['city'])
                    if loc.get('street'):
                        street = loc['street']
                        if loc.get('house_number'):
                            street += f", {loc['house_number']}"
                        address_parts.append(street)
                    address_str = ", ".join(address_parts) if address_parts else ""
                    theatre_name = loc.get('theatre_name', '')
                    hall_name = loc.get('hall_name', '')
                    location_display = f"{theatre_name}, {hall_name}" if theatre_name and hall_name else (theatre_name or hall_name or 'Неизвестно')
                    location_choices.append(location_display + (f" ({address_str})" if address_str else ""))
                self.location_choice = wx.Choice(panel, -1, choices=location_choices)
                if self.performance_data.get('location_id'):
                    for i, loc in enumerate(self.locations):
                        if loc['id'] == self.performance_data['location_id']:
                            self.location_choice.SetSelection(i)
                            break
                sizer.Add(self.location_choice, 0, wx.EXPAND | wx.ALL, 5)
            except Exception as e:
                logging.error(f"Ошибка загрузки мест проведения: {e}")
                self.location_choice = wx.Choice(panel, -1, choices=[])
                self.locations = []
                sizer.Add(self.location_choice, 0, wx.EXPAND | wx.ALL, 5)
        else:
            self.location_choice = wx.Choice(panel, -1, choices=[])
            self.locations = []
            sizer.Add(self.location_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_location = wx.StaticText(panel, -1, "")
        error_label_location.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_location.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_location, 0, wx.LEFT | wx.BOTTOM, 5)
        
        self.add_validated_field(self.location_choice, lambda v: self.location_choice.GetSelection() != wx.NOT_FOUND, required=True, error_label=error_label_location)
        self.add_validated_field(self.datetime, lambda v: self.datetime.is_valid() if hasattr(self.datetime, 'is_valid') else len(v.strip()) > 0, required=True, error_label=error_label_datetime)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        
        panel.SetSizer(sizer)
        # Убираем ограничение минимального размера для лучшей адаптивности
        self.validate_all()
        
    def get_data(self):
        production_id = None
        production_selection = self.production_choice.GetSelection()
        if production_selection > 0 and self.productions:
            production_id = self.productions[production_selection - 1]['id']  # -1 потому что первый элемент пустой
        
        location_id = None
        if self.location_choice.GetSelection() != wx.NOT_FOUND and self.locations:
            location_id = self.locations[self.location_choice.GetSelection()]['id']
        
        datetime_value = self.datetime.get_datetime_value() if hasattr(self.datetime, 'get_datetime_value') else self.datetime.GetValue()
        
        return {
            'production_id': production_id,
            'datetime': datetime_value,
            'location_id': location_id
        }

class ViewPerformanceDialog(wx.Dialog):
    def __init__(self, parent, title, performance_data):
        super().__init__(parent, title=title, size=(700, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.performance_data = performance_data
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "📅 Просмотр спектакля")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        sizer.Add(wx.StaticText(panel, -1, "Постановка:"), 0, wx.ALL, 5)
        production_id = self.performance_data.get('production_id', 1)
        future = run_async(db_manager.get_all_productions())
        productions = future.result(timeout=10) if future else []
        production_title = next((production['title'] for production in productions if production['id'] == production_id), "Неизвестно")
        self.production = wx.TextCtrl(panel, -1, production_title, style=wx.TE_READONLY)
        sizer.Add(self.production, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Дата и время:"), 0, wx.ALL, 5)
        datetime_val = self.performance_data.get('datetime', '')
        datetime_str = format_datetime_for_display(datetime_val)
        self.datetime = wx.TextCtrl(panel, -1, datetime_str, style=wx.TE_READONLY)
        sizer.Add(self.datetime, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Место проведения:"), 0, wx.ALL, 5)
        location_id = self.performance_data.get('location_id', None)
        location_name = "Неизвестно"
        if location_id:
            future = run_async(db_manager.get_location_by_id(location_id))
            if future:
                try:
                    location = future.result(timeout=10)
                    if location:
                        theatre_name = location.get('theatre_name', '')
                        hall_name = location.get('hall_name', '')
                        location_name = f"{theatre_name}, {hall_name}" if theatre_name and hall_name else (theatre_name or hall_name or 'Неизвестно')
                except:
                    pass
        self.location = wx.TextCtrl(panel, -1, location_name, style=wx.TE_READONLY)
        sizer.Add(self.location, 0, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        # Убираем ограничение минимального размера для лучшей адаптивности

class EditRehearsalDialog(ValidatedDialog):
    def __init__(self, parent, title, rehearsal_data=None):
        super().__init__(parent, title, size=(1100, 900))
        self.rehearsal_data = rehearsal_data or {}
        self.productions = []
        self.locations = []
        self.all_actors = []
        self.actor_ids = []  # Список ID актеров для репетиции
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        
        # Актеры будут загружены после создания UI в _finalize_actors_loading
    
    def load_all_actors(self):
        """Загружает всех актеров и обновляет список."""
        future = run_async(db_manager.get_all_actors())
        if future:
            try:
                self.all_actors = future.result(timeout=10) or []
                # Обновляем список актеров после загрузки, если список уже создан
                if hasattr(self, 'actors_listbox') and self.actors_listbox:
                    self.update_actors_listbox()
            except Exception as e:
                logging.error(f"Не удалось загрузить список актеров: {e}")
    
    def load_rehearsal_actors(self, rehearsal_id):
        """Загружает актеров репетиции и обновляет список."""
        future = run_async(db_manager.get_actors_for_rehearsal(rehearsal_id))
        if future:
            try:
                actors = future.result(timeout=10) or []
                self.actor_ids = [actor['id'] for actor in actors]
                # Убеждаемся, что все актеры загружены перед обновлением
                if not self.all_actors:
                    self.load_all_actors()
                self.update_actors_listbox()
            except Exception as e:
                logging.error(f"Не удалось загрузить актеров репетиции: {e}")
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        
        label = wx.StaticText(panel, -1, "Постановка:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_productions())
        if future:
            try:
                self.productions = future.result(timeout=10) or []
                production_choices = [''] + [production['title'] for production in self.productions]
                self.production_choice = wx.Choice(panel, -1, choices=production_choices)
                if self.rehearsal_data.get('production_id'):
                    prod_idx = next((i+1 for i, prod in enumerate(self.productions) if prod['id'] == self.rehearsal_data['production_id']), 0)
                    self.production_choice.SetSelection(prod_idx)
                else:
                    self.production_choice.SetSelection(0)
                sizer.Add(self.production_choice, 0, wx.EXPAND | wx.ALL, 5)
            except Exception as e:
                logging.error(f"Ошибка загрузки постановок: {e}")
                self.production_choice = wx.Choice(panel, -1, choices=[''])
                sizer.Add(self.production_choice, 0, wx.EXPAND | wx.ALL, 5)
        else:
            self.production_choice = wx.Choice(panel, -1, choices=[''])
            sizer.Add(self.production_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_production = wx.StaticText(panel, -1, "")
        error_label_production.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_production.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_production, 0, wx.LEFT | wx.BOTTOM, 5)
        
        def validate_production(selection):
            return selection > 0  # Первый элемент - пустой
        
        self.add_validated_field(self.production_choice, validate_production, required=True, error_label=error_label_production)
        
        label = wx.StaticText(panel, -1, "Дата и время:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        datetime_val = self.rehearsal_data.get('datetime', '')
        # Преобразуем в формат YYYY-MM-DD HH:MM:SS
        if hasattr(datetime_val, 'strftime'):
            datetime_val = datetime_val.strftime('%Y-%m-%d %H:%M:%S')
        elif datetime_val:
            # Если это строка, пробуем распарсить
            try:
                # Пробуем разные форматы
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y%m%d%H%M%S']:
                    try:
                        dt = datetime.strptime(str(datetime_val), fmt)
                        datetime_val = dt.strftime('%Y-%m-%d %H:%M:%S')
                        break
                    except:
                        continue
            except:
                pass
        self.datetime = AutoCompleteDateTimeCtrl(panel, -1, value=str(datetime_val) if datetime_val else '')
        self.datetime.SetHint("YYYY-MM-DD HH:MM:SS (введите цифры, разделители добавятся автоматически)")
        sizer.Add(self.datetime, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_datetime = wx.StaticText(panel, -1, "")
        error_label_datetime.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_datetime.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_datetime, 0, wx.LEFT | wx.BOTTOM, 5)
        
        label = wx.StaticText(panel, -1, "Место проведения:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_locations())
        if future:
            try:
                self.locations = future.result(timeout=10) or []
                location_choices = []
                for loc in self.locations:
                    address_parts = []
                    if loc.get('city'):
                        address_parts.append(loc['city'])
                    if loc.get('street'):
                        street = loc['street']
                        if loc.get('house_number'):
                            street += f", {loc['house_number']}"
                        address_parts.append(street)
                    address_str = ", ".join(address_parts) if address_parts else ""
                    theatre_name = loc.get('theatre_name', '')
                    hall_name = loc.get('hall_name', '')
                    location_display = f"{theatre_name}, {hall_name}" if theatre_name and hall_name else (theatre_name or hall_name or 'Неизвестно')
                    location_choices.append(location_display + (f" ({address_str})" if address_str else ""))
                self.location_choice = wx.Choice(panel, -1, choices=location_choices)
                if self.rehearsal_data.get('location_id'):
                    for i, loc in enumerate(self.locations):
                        if loc['id'] == self.rehearsal_data['location_id']:
                            self.location_choice.SetSelection(i)
                            break
                sizer.Add(self.location_choice, 0, wx.EXPAND | wx.ALL, 5)
            except Exception as e:
                logging.error(f"Ошибка загрузки мест проведения: {e}")
                self.location_choice = wx.Choice(panel, -1, choices=[])
                self.locations = []
                sizer.Add(self.location_choice, 0, wx.EXPAND | wx.ALL, 5)
        else:
            self.location_choice = wx.Choice(panel, -1, choices=[])
            self.locations = []
            sizer.Add(self.location_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_location = wx.StaticText(panel, -1, "")
        error_label_location.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_location.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_location, 0, wx.LEFT | wx.BOTTOM, 5)
        
        error_label_datetime = wx.StaticText(panel, -1, "")
        error_label_datetime.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_datetime.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_datetime, 0, wx.LEFT | wx.BOTTOM, 5)
        
        self.add_validated_field(self.location_choice, lambda v: self.location_choice.GetSelection() != wx.NOT_FOUND, required=True, error_label=error_label_location)
        self.add_validated_field(self.datetime, lambda v: self.datetime.is_valid() if hasattr(self.datetime, 'is_valid') else len(v.strip()) > 0, required=True, error_label=error_label_datetime)
        
        # --- Список актеров для репетиции ---
        actors_sizer = wx.BoxSizer(wx.VERTICAL)
        actors_sizer.Add(wx.StaticText(panel, -1, "Актеры на репетиции:"), 0, wx.ALL, 5)
        self.actors_listbox = wx.ListBox(panel, -1, style=wx.LB_MULTIPLE, size=(-1, 200))
        actors_sizer.Add(self.actors_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        actors_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_actor_btn = wx.Button(panel, -1, "Добавить актера")
        self.remove_actor_btn = wx.Button(panel, -1, "Удалить актера")
        actors_btn_sizer.Add(self.add_actor_btn, 0, wx.RIGHT, 5)
        actors_btn_sizer.Add(self.remove_actor_btn, 0)
        actors_sizer.Add(actors_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        
        self.add_actor_btn.Bind(wx.EVT_BUTTON, self.on_add_actor)
        self.remove_actor_btn.Bind(wx.EVT_BUTTON, self.on_remove_actor)
        
        sizer.Add(actors_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        
        panel.SetSizer(sizer)
        self.SetMinSize((800, 700))
        self.validate_all()
        
        # После создания UI загружаем актеров и обновляем список
        wx.CallLater(100, self._finalize_actors_loading)
    
    def _finalize_actors_loading(self):
        """Финальная загрузка актеров после создания UI."""
        if not self.all_actors:
            self.load_all_actors()
        # Если это редактирование и актеры еще не загружены, загружаем их
        if self.rehearsal_data.get('id') and not self.actor_ids:
            self.load_rehearsal_actors(self.rehearsal_data['id'])
        # Обновляем список актеров
        if hasattr(self, 'actors_listbox') and self.actors_listbox:
            self.update_actors_listbox()
    
    def on_add_actor(self, event):
        # Показываем диалог выбора актеров
        available_actors = [actor for actor in self.all_actors if actor['id'] not in self.actor_ids]
        if not available_actors:
            show_error("Все актеры уже добавлены в репетицию.")
            return
        
        actor_choices = [f"{actor['full_name']} (ID: {actor['id']})" for actor in available_actors]
        
        dialog = wx.Dialog(self, title="Добавить актера", size=(600, 500))
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "Выберите актера:"), 0, wx.ALL, 10)
        actor_choice = wx.Choice(panel, -1, choices=actor_choices)
        sizer.Add(actor_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        if dialog.ShowModal() == wx.ID_OK:
            selected_idx = actor_choice.GetSelection()
            if selected_idx != wx.NOT_FOUND:
                selected_actor = available_actors[selected_idx]
                if selected_actor['id'] not in self.actor_ids:
                    self.actor_ids.append(selected_actor['id'])
                    self.update_actors_listbox()
        
        dialog.Destroy()
    
    def on_remove_actor(self, event):
        selected_indices = self.actors_listbox.GetSelections()
        if not selected_indices:
            show_error("Выберите актеров для удаления.")
            return
        
        # Удаляем в обратном порядке, чтобы индексы не сдвигались
        for idx in reversed(selected_indices):
            actor_str = self.actors_listbox.GetString(idx)
            try:
                actor_id_str = actor_str.split('(ID: ')[1].split(')')[0]
                actor_id = int(actor_id_str)
                if actor_id in self.actor_ids:
                    self.actor_ids.remove(actor_id)
            except Exception as e:
                logging.error(f"Ошибка удаления актера: {e}")
        
        self.update_actors_listbox()
    
    def update_actors_listbox(self):
        self.actors_listbox.Clear()
        items = []
        for actor_id in self.actor_ids:
            actor = next((a for a in self.all_actors if a['id'] == actor_id), None)
            if actor:
                items.append(f"{actor['full_name']} (ID: {actor_id})")
        
        if items:
            self.actors_listbox.InsertItems(items, 0)
        
    def get_data(self):
        production_id = None
        production_selection = self.production_choice.GetSelection()
        if production_selection > 0 and self.productions:
            production_id = self.productions[production_selection - 1]['id']  # -1 потому что первый элемент пустой
        
        location_id = None
        if self.location_choice.GetSelection() != wx.NOT_FOUND and self.locations:
            location_id = self.locations[self.location_choice.GetSelection()]['id']
        
        datetime_value = self.datetime.get_datetime_value() if hasattr(self.datetime, 'get_datetime_value') else self.datetime.GetValue()
        
        return {
            'production_id': production_id,
            'datetime': datetime_value,
            'location_id': location_id,
            'actor_ids': self.actor_ids.copy() if hasattr(self, 'actor_ids') else []
        }

class ViewRehearsalDialog(wx.Dialog):
    def __init__(self, parent, title, rehearsal_data):
        super().__init__(parent, title=title, size=(800, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.rehearsal_data = rehearsal_data
        self.rehearsal_id = rehearsal_data.get('id')
        self.actors_data = []
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        if self.rehearsal_id:
            self.load_actors()
        
    def load_actors(self):
        """Загружает актеров репетиции"""
        if not self.rehearsal_id:
            return
        
        future = run_async(db_manager.get_actors_for_rehearsal(self.rehearsal_id))
        if future:
            try:
                self.actors_data = future.result(timeout=10) or []
                self.update_actors_listbox()
            except Exception as e:
                logging.error(f"Ошибка загрузки актеров: {e}")
    
    def update_actors_listbox(self):
        """Обновляет список актеров"""
        if not hasattr(self, 'actors_listbox'):
            return
        
        self.actors_listbox.Clear()
        items = []
        for actor in self.actors_data:
            actor_name = actor.get('full_name', 'Неизвестно')
            items.append(actor_name)
        
        if items:
            self.actors_listbox.InsertItems(items, 0)
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "🔄 Просмотр репетиции")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        # Основная информация
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Постановка:"), 0, wx.ALL, 5)
        production_id = self.rehearsal_data.get('production_id', 1)
        future = run_async(db_manager.get_all_productions())
        productions = future.result(timeout=10) if future else []
        production_title = next((production['title'] for production in productions if production['id'] == production_id), "Неизвестно")
        self.production = wx.TextCtrl(panel, -1, production_title, style=wx.TE_READONLY)
        left_sizer.Add(self.production, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Дата и время:"), 0, wx.ALL, 5)
        datetime_val = self.rehearsal_data.get('datetime', '')
        datetime_str = format_datetime_for_display(datetime_val)
        self.datetime = wx.TextCtrl(panel, -1, datetime_str, style=wx.TE_READONLY)
        left_sizer.Add(self.datetime, 0, wx.EXPAND | wx.ALL, 5)
        
        left_sizer.Add(wx.StaticText(panel, -1, "Место проведения:"), 0, wx.ALL, 5)
        location_id = self.rehearsal_data.get('location_id', None)
        location_name = "Неизвестно"
        if location_id:
            future = run_async(db_manager.get_location_by_id(location_id))
            if future:
                try:
                    location = future.result(timeout=10)
                    if location:
                        theatre_name = location.get('theatre_name', '')
                        hall_name = location.get('hall_name', '')
                        location_name = f"{theatre_name}, {hall_name}" if theatre_name and hall_name else (theatre_name or hall_name or 'Неизвестно')
                except:
                    pass
        self.location = wx.TextCtrl(panel, -1, location_name, style=wx.TE_READONLY)
        left_sizer.Add(self.location, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Актеры
        actors_sizer = wx.BoxSizer(wx.VERTICAL)
        actors_sizer.Add(wx.StaticText(panel, -1, "👥 Актеры на репетиции:"), 0, wx.ALL, 5)
        self.actors_listbox = wx.ListBox(panel, -1, style=wx.LB_SINGLE, size=(300, 200))
        actors_sizer.Add(self.actors_listbox, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(actors_sizer, 1, wx.EXPAND | wx.LEFT, 5)
        sizer.Add(main_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        self.SetMinSize((900, 700))

class EditRoleDialog(ValidatedDialog):
    def __init__(self, parent, title, role_data=None):
        super().__init__(parent, title, size=(900, 750))
        self.role_data = role_data or {}
        self.plays = []
        self.init_ui()
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        
        label = wx.StaticText(panel, -1, "Название роли:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        self.title = wx.TextCtrl(panel, -1, self.role_data.get('title', ''))
        self.title.SetHint("Введите название роли")
        sizer.Add(self.title, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_title = wx.StaticText(panel, -1, "")
        error_label_title.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_title.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_title, 0, wx.LEFT | wx.BOTTOM, 5)
        
        label = wx.StaticText(panel, -1, "Пьеса:*")
        label.SetForegroundColour(wx.Colour(255, 0, 0))
        sizer.Add(label, 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_plays())
        if future:
            try:
                self.plays = future.result(timeout=10) or []
                play_choices = [''] + [play['title'] for play in self.plays]
                self.play_choice = wx.Choice(panel, -1, choices=play_choices)
                if self.role_data.get('play_id'):
                    play_idx = next((i+1 for i, play in enumerate(self.plays) if play['id'] == self.role_data['play_id']), 0)
                    self.play_choice.SetSelection(play_idx)
                else:
                    self.play_choice.SetSelection(0)
                sizer.Add(self.play_choice, 0, wx.EXPAND | wx.ALL, 5)
            except Exception as e:
                logging.error(f"Ошибка загрузки пьес: {e}")
                self.play_choice = wx.Choice(panel, -1, choices=[''])
                sizer.Add(self.play_choice, 0, wx.EXPAND | wx.ALL, 5)
        else:
            self.play_choice = wx.Choice(panel, -1, choices=[''])
            sizer.Add(self.play_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_play = wx.StaticText(panel, -1, "")
        error_label_play.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_play.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_play, 0, wx.LEFT | wx.BOTTOM, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Описание роли:"), 0, wx.ALL, 5)
        self.description = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(-1, 250))
        self.description.SetValue(self.role_data.get('description', ''))
        sizer.Add(self.description, 1, wx.EXPAND | wx.ALL, 5)
        
        # Валидация для пьесы
        def validate_play(selection):
            return selection > 0  # Первый элемент - пустой
        
        self.add_validated_field(self.title, lambda v: len(v.strip()) > 0, required=True, error_label=error_label_title)
        self.add_validated_field(self.play_choice, validate_play, required=True, error_label=error_label_play)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        
        panel.SetSizer(sizer)
        self.SetMinSize((800, 650))
        self.validate_all()
        
    def get_data(self):
        play_id = None
        play_selection = self.play_choice.GetSelection()
        if play_selection > 0 and self.plays:
            play_id = self.plays[play_selection - 1]['id']  # -1 потому что первый элемент пустой
        
        return {
            'title': self.title.GetValue().strip(),
            'description': self.description.GetValue(),
            'play_id': play_id
        }

class ViewRoleDialog(wx.Dialog):
    def __init__(self, parent, title, role_data):
        super().__init__(parent, title=title, size=(700, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.role_data = role_data
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "🎪 Просмотр роли")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        sizer.Add(wx.StaticText(panel, -1, "Название роли:"), 0, wx.ALL, 5)
        self.title = wx.TextCtrl(panel, -1, self.role_data.get('title', ''), style=wx.TE_READONLY)
        sizer.Add(self.title, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Пьеса:"), 0, wx.ALL, 5)
        play_id = self.role_data.get('play_id', 1)
        future = run_async(db_manager.get_all_plays())
        plays = future.result(timeout=10) if future else []
        play_title = next((play['title'] for play in plays if play['id'] == play_id), "Неизвестно")
        self.play = wx.TextCtrl(panel, -1, play_title, style=wx.TE_READONLY)
        sizer.Add(self.play, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Описание роли:"), 0, wx.ALL, 5)
        self.description = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 250))
        self.description.SetValue(self.role_data.get('description', ''))
        sizer.Add(self.description, 1, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)
        self.SetMinSize((800, 650))

class EditLocationDialog(ValidatedDialog):
    def __init__(self, parent, title, location_data=None):
        super().__init__(parent, title, size=(1000, 800))
        self.location_data = location_data or {}
        self.theatres = []
        self.init_ui()
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "Театр:*"), 0, wx.ALL, 5)
        future = run_async(db_manager.get_all_theatres())
        if future:
            try:
                self.theatres = future.result(timeout=10) or []
                theatre_choices = [f"{t['name']}" for t in self.theatres]
                self.theatre_choice = wx.Choice(panel, -1, choices=theatre_choices)
                if self.location_data.get('theatre_id'):
                    for i, theatre in enumerate(self.theatres):
                        if theatre['id'] == self.location_data['theatre_id']:
                            self.theatre_choice.SetSelection(i)
                            break
                sizer.Add(self.theatre_choice, 0, wx.EXPAND | wx.ALL, 5)
            except:
                self.theatre_choice = wx.Choice(panel, -1, choices=[])
                self.theatres = []
                sizer.Add(self.theatre_choice, 0, wx.EXPAND | wx.ALL, 5)
        else:
            self.theatre_choice = wx.Choice(panel, -1, choices=[])
            self.theatres = []
            sizer.Add(self.theatre_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        error_label_theatre = wx.StaticText(panel, -1, "")
        error_label_theatre.SetForegroundColour(wx.Colour(255, 0, 0))
        error_label_theatre.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(error_label_theatre, 0, wx.LEFT | wx.BOTTOM, 5)
        self.add_validated_field(self.theatre_choice, lambda v: self.theatre_choice.GetSelection() != wx.NOT_FOUND, required=True, error_label=error_label_theatre)
        
        sizer.Add(wx.StaticText(panel, -1, "Название зала/сцены:*"), 0, wx.ALL, 5)
        self.hall_name = wx.TextCtrl(panel, -1, self.location_data.get('hall_name', ''))
        self.hall_name.SetHint("Введите название зала или сцены")
        sizer.Add(self.hall_name, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.hall_name, lambda v: len(v.strip()) > 0)
        
        sizer.Add(wx.StaticText(panel, -1, "Вместимость:"), 0, wx.ALL, 5)
        capacity_value = self.location_data.get('capacity', '')
        self.capacity = ValidatedTextCtrl(panel, 
                                         validator_func=lambda v: (not v.strip() or v.strip().isdigit()),
                                         error_message="Вместимость должна быть числом")
        self.capacity.SetValue(str(capacity_value) if capacity_value else '')
        self.capacity.SetHint("Количество мест (необязательно)")
        sizer.Add(self.capacity, 0, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        
        panel.SetSizer(sizer)
        self.validate_all()
        
    def get_data(self):
        theatre_id = None
        if self.theatre_choice.GetSelection() != wx.NOT_FOUND and self.theatres:
            theatre_id = self.theatres[self.theatre_choice.GetSelection()]['id']
        capacity_str = self.capacity.GetValue().strip()
        capacity = int(capacity_str) if capacity_str and capacity_str.isdigit() else None
        return {
            'theatre_id': theatre_id,
            'hall_name': self.hall_name.GetValue().strip(),
            'capacity': capacity
        }

class ViewLocationDialog(wx.Dialog):
    def __init__(self, parent, title, location_data):
        super().__init__(parent, title=title, size=(700, 700))
        self.location_data = location_data
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "📍 Просмотр локации")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        sizer.Add(wx.StaticText(panel, -1, "Театр:"), 0, wx.ALL, 5)
        theatre_name = self.location_data.get('theatre_name', 'Неизвестно')
        self.theatre = wx.TextCtrl(panel, -1, theatre_name, style=wx.TE_READONLY)
        sizer.Add(self.theatre, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Зал/Сцена:"), 0, wx.ALL, 5)
        hall_name = self.location_data.get('hall_name', 'Неизвестно')
        self.hall_name = wx.TextCtrl(panel, -1, hall_name, style=wx.TE_READONLY)
        sizer.Add(self.hall_name, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Город:"), 0, wx.ALL, 5)
        city = self.location_data.get('city', '')
        self.city = wx.TextCtrl(panel, -1, city, style=wx.TE_READONLY)
        sizer.Add(self.city, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Улица:"), 0, wx.ALL, 5)
        street = self.location_data.get('street', '')
        self.street = wx.TextCtrl(panel, -1, street, style=wx.TE_READONLY)
        sizer.Add(self.street, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Номер дома:"), 0, wx.ALL, 5)
        self.house_number = wx.TextCtrl(panel, -1, self.location_data.get('house_number', ''), style=wx.TE_READONLY)
        sizer.Add(self.house_number, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Почтовый индекс:"), 0, wx.ALL, 5)
        self.postal_code = wx.TextCtrl(panel, -1, self.location_data.get('postal_code', ''), style=wx.TE_READONLY)
        sizer.Add(self.postal_code, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Вместимость:"), 0, wx.ALL, 5)
        capacity = self.location_data.get('capacity', '')
        self.capacity = wx.TextCtrl(panel, -1, str(capacity) if capacity else '', style=wx.TE_READONLY)
        sizer.Add(self.capacity, 0, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)

class EditTheatreDialog(ValidatedDialog):
    def __init__(self, parent, title, theatre_data=None):
        super().__init__(parent, title, size=(900, 800))
        self.theatre_data = theatre_data or {}
        self.init_ui()
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(panel, -1, "Название театра:*"), 0, wx.ALL, 5)
        self.name = wx.TextCtrl(panel, -1, self.theatre_data.get('name', ''))
        self.name.SetHint("Введите название театра")
        sizer.Add(self.name, 0, wx.EXPAND | wx.ALL, 5)
        self.add_validated_field(self.name, lambda v: len(v.strip()) > 0)
        
        sizer.Add(wx.StaticText(panel, -1, "Город:"), 0, wx.ALL, 5)
        self.city = wx.TextCtrl(panel, -1, self.theatre_data.get('city', ''))
        self.city.SetHint("Город (необязательно)")
        sizer.Add(self.city, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Улица:"), 0, wx.ALL, 5)
        self.street = wx.TextCtrl(panel, -1, self.theatre_data.get('street', ''))
        self.street.SetHint("Название улицы (необязательно)")
        sizer.Add(self.street, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Номер дома:"), 0, wx.ALL, 5)
        self.house_number = wx.TextCtrl(panel, -1, self.theatre_data.get('house_number', ''))
        self.house_number.SetHint("Номер дома (необязательно)")
        sizer.Add(self.house_number, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Почтовый индекс:"), 0, wx.ALL, 5)
        self.postal_code = wx.TextCtrl(panel, -1, self.theatre_data.get('postal_code', ''))
        self.postal_code.SetHint("Почтовый индекс (необязательно)")
        sizer.Add(self.postal_code, 0, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        ok_btn.SetMinSize((80, 30))
        cancel_btn.SetMinSize((80, 30))
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.set_ok_button(ok_btn)
        
        panel.SetSizer(sizer)
        self.validate_all()
        
    def get_data(self):
        return {
            'name': self.name.GetValue().strip(),
            'city': self.city.GetValue().strip() or None,
            'street': self.street.GetValue().strip() or None,
            'house_number': self.house_number.GetValue().strip() or None,
            'postal_code': self.postal_code.GetValue().strip() or None
        }

class ViewTheatreDialog(wx.Dialog):
    def __init__(self, parent, title, theatre_data):
        super().__init__(parent, title=title, size=(600, 600))
        self.theatre_data = theatre_data
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))
        
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title_text = wx.StaticText(panel, -1, "🎭 Просмотр театра")
        title_text.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        sizer.Add(wx.StaticText(panel, -1, "Название:"), 0, wx.ALL, 5)
        self.name = wx.TextCtrl(panel, -1, self.theatre_data.get('name', ''), style=wx.TE_READONLY)
        sizer.Add(self.name, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Город:"), 0, wx.ALL, 5)
        city = self.theatre_data.get('city', '')
        self.city = wx.TextCtrl(panel, -1, city, style=wx.TE_READONLY)
        sizer.Add(self.city, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Улица:"), 0, wx.ALL, 5)
        street = self.theatre_data.get('street', '')
        self.street = wx.TextCtrl(panel, -1, street, style=wx.TE_READONLY)
        sizer.Add(self.street, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Номер дома:"), 0, wx.ALL, 5)
        self.house_number = wx.TextCtrl(panel, -1, self.theatre_data.get('house_number', ''), style=wx.TE_READONLY)
        sizer.Add(self.house_number, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(wx.StaticText(panel, -1, "Почтовый индекс:"), 0, wx.ALL, 5)
        self.postal_code = wx.TextCtrl(panel, -1, self.theatre_data.get('postal_code', ''), style=wx.TE_READONLY)
        sizer.Add(self.postal_code, 0, wx.EXPAND | wx.ALL, 5)
        
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Закрыть")
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        
        panel.SetSizer(sizer)

def create_table_panel(parent, table_name):
    try:
        panel = wx.Panel(parent)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        
        control_panel_top = wx.Panel(panel)
        control_sizer_top = wx.BoxSizer(wx.HORIZONTAL)
        
        back_btn = wx.Button(control_panel_top, -1, "🏠 Главный экран")
        back_btn.SetMinSize((120, 40))
        back_btn.Bind(wx.EVT_BUTTON, lambda e: show_dashboard(parent))
        control_sizer_top.Add(back_btn, 0, wx.RIGHT, 10)
        
        title = wx.StaticText(control_panel_top, -1, f"📊 {table_name}")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        control_sizer_top.Add(title, 1, wx.ALIGN_CENTER_VERTICAL)
        
        fullscreen_btn = wx.Button(control_panel_top, -1, "⛶ Полный экран")
        fullscreen_btn.SetMinSize((120, 40))
        control_sizer_top.Add(fullscreen_btn, 0, wx.LEFT, 10)
        
        def toggle_fullscreen_table(event):
            try:
                frame = panel.GetTopLevelParent()
                if not frame or not isinstance(frame, wx.Frame):
                    # Пытаемся найти frame другим способом
                    parent = panel.GetParent()
                    while parent and not isinstance(parent, wx.Frame):
                        parent = parent.GetParent()
                    frame = parent
                
                if frame:
                    if frame.IsFullScreen():
                        frame.ShowFullScreen(False, wx.FULLSCREEN_ALL)
                        fullscreen_btn.SetLabel("⛶ Полный экран")
                    else:
                        frame.ShowFullScreen(True, wx.FULLSCREEN_ALL)
                        fullscreen_btn.SetLabel("⛶ Обычный режим")
            except Exception as e:
                logging.error(f"Ошибка переключения полного экрана: {e}")
                wx.MessageBox(f"Не удалось переключить полный экран: {e}", "Ошибка", wx.OK | wx.ICON_ERROR)
        
        fullscreen_btn.Bind(wx.EVT_BUTTON, toggle_fullscreen_table)
        
        control_panel_top.SetSizer(control_sizer_top)
        panel_sizer.Add(control_panel_top, 0, wx.EXPAND | wx.ALL, 10)
        
        # Панель поиска
        search_panel = wx.Panel(panel)
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = wx.StaticText(search_panel, -1, "🔍 Поиск:")
        search_sizer.Add(search_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        search_ctrl = wx.SearchCtrl(search_panel, -1, size=(300, -1), style=wx.TE_PROCESS_ENTER)
        search_ctrl.SetHint("Введите текст для поиска...")
        search_sizer.Add(search_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        # Подсказка о сортировке
        sort_hint = wx.StaticText(search_panel, -1, "💡 Кликните на заголовок колонки для сортировки")
        sort_hint.SetForegroundColour(wx.Colour(100, 100, 100))
        sort_hint.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        search_sizer.Add(sort_hint, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        search_panel.SetSizer(search_sizer)
        panel_sizer.Add(search_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        grid = wx.grid.Grid(panel)
        grid.CreateGrid(0, 3)
        wx.CallAfter(lambda: theme_manager.apply_theme(grid))
        # Подсказка о сортировке: клик по заголовку колонки для сортировки
        grid.SetColLabelAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        # Делаем таблицу read-only - нельзя редактировать ячейки напрямую
        grid.EnableEditing(False)
        grid.EnableGridLines(True)
        # Настройка обводки для выделенных ячеек в темном стиле
        def setup_grid_selection_border():
            if theme_manager.get_current_theme_name() == 'dark':
                try:
                    # Увеличиваем ширину обводки
                    grid.SetCellHighlightPenWidth(3)
                    grid.SetCellHighlightROPenWidth(3)
                    # Устанавливаем яркий цвет обводки для выделенных ячеек
                    highlight_pen = wx.Pen(wx.Colour(100, 200, 255), 3)  # Яркий голубой
                    grid.SetDefaultCellHighlightPen(highlight_pen)
                    grid.SetDefaultCellHighlightROPen(highlight_pen)
                except Exception as e:
                    logging.debug(f"Не удалось установить обводку для grid: {e}")
        wx.CallAfter(setup_grid_selection_border)
        panel_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 10)
        
        original_data = []
        original_headers = []
        sort_column = 0
        sort_ascending = True
        
        def apply_search(search_text, sort_col=None, sort_asc=None):
            """Применяет поисковый фильтр к данным таблицы через БД с сортировкой через aiomysql"""
            # Используем переданные параметры сортировки или значения по умолчанию
            actual_sort_col = sort_col if sort_col is not None else sort_column
            actual_sort_asc = sort_asc if sort_asc is not None else sort_ascending
            
            async def search_in_db():
                """Поиск в БД с сортировкой через aiomysql"""
                try:
                    if not db_initialized or not db_manager:
                        logging.error("База данных не инициализирована для поиска")
                        return
                    
                    # Маппинг заголовков колонок на имена полей БД для каждой таблицы
                    column_mapping = {
                        "Актеры": {0: 'id', 1: 'full_name', 2: 'experience'},
                        "Авторы": {0: 'id', 1: 'full_name', 2: 'biography'},
                        "Режиссеры": {0: 'id', 1: 'full_name', 2: 'biography'},
                        "Пьесы": {0: 'id', 1: 'title', 2: 'genre', 3: 'year_written', 4: 'description'},
                        "Постановки": {0: 'id', 1: 'title', 2: 'production_date', 3: 'description'},
                        "Спектакли": {0: 'id', 1: 'datetime'},
                        "Репетиции": {0: 'id', 1: 'datetime'},
                        "Роли": {0: 'id', 1: 'title', 2: 'description'},
                        "Локации": {0: 'id', 1: 'hall_name', 2: 'theatre_name', 3: 'capacity'},
                        "Театры": {0: 'id', 1: 'name', 2: 'city', 3: 'street', 4: 'house_number', 5: 'postal_code'}
                    }
                    
                    # Определяем колонку для сортировки
                    db_column = 'id'  # по умолчанию сортируем по ID
                    if actual_sort_col in column_mapping.get(table_name, {}):
                        db_column = column_mapping[table_name][actual_sort_col]
                    
                    data = []
                    headers = []
                    
                    # Если есть поисковый текст - используем поисковые методы
                    if search_text:
                        search_methods = {
                            "Актеры": db_manager.search_actors_sorted,
                            "Авторы": db_manager.search_authors_sorted,
                            "Режиссеры": db_manager.search_directors_sorted,
                            "Пьесы": db_manager.search_plays_sorted,
                            "Постановки": db_manager.search_productions_sorted,
                            "Спектакли": db_manager.search_performances_sorted,
                            "Репетиции": db_manager.search_rehearsals_sorted,
                            "Роли": db_manager.search_roles_sorted,
                            "Локации": db_manager.search_locations_sorted,
                            "Театры": db_manager.search_theatres_sorted
                        }
                        
                        search_method = search_methods.get(table_name)
                        if search_method:
                            results = await search_method(search_text, db_column, actual_sort_asc)
                            
                            # Если есть результаты поиска - преобразуем их
                            if results:
                                data = await convert_results_to_grid_format(results, table_name)
                    else:
                        # Если поиск пустой - загружаем все данные с сортировкой
                        load_methods = {
                            "Актеры": lambda: db_manager.get_all_actors_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Авторы": lambda: db_manager.get_all_authors_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Режиссеры": lambda: db_manager.get_all_directors_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Пьесы": lambda: db_manager.get_all_plays_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Постановки": lambda: db_manager.get_all_productions_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Спектакли": lambda: db_manager.get_all_performances_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Репетиции": lambda: db_manager.get_all_rehearsals_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Роли": lambda: db_manager.get_all_roles_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Локации": lambda: db_manager.get_all_locations_sorted(db_column, actual_sort_asc, force_refresh=True),
                            "Театры": lambda: db_manager.get_all_theatres_sorted(db_column, actual_sort_asc, force_refresh=True)
                        }
                        
                        load_method = load_methods.get(table_name)
                        if load_method:
                            results = await load_method()
                            if results:
                                data = await convert_results_to_grid_format(results, table_name)
                    
                    # Получаем заголовки таблицы
                    _, table_headers_temp = await get_sample_data()
                    headers = table_headers_temp.get(table_name, [])
                    
                    # Обновляем grid с результатами
                    def update_with_results():
                        nonlocal original_data, original_headers
                        original_data = data[:] if data else []
                        original_headers = headers[:] if headers else []
                        safe_grid_update(data, headers)
                    
                    wx.CallAfter(update_with_results)
                    
                except Exception as e:
                    logging.error(f"Ошибка поиска в БД: {e}", exc_info=True)
                    # В случае ошибки показываем пустую таблицу
                    wx.CallAfter(lambda: safe_grid_update([], []))
            
            # Запускаем поиск в БД
            run_async(search_in_db())

        async def convert_results_to_grid_format(results, table_name):
            """Преобразует результаты БД в формат для отображения в grid"""
            data = []
            
            # Загружаем дополнительные данные для связей
            plays_dict = {}
            directors_dict = {}
            locations_dict = {}
            productions_dict = {}
            
            if table_name in ["Постановки", "Спектакли", "Репетиции", "Роли"]:
                all_plays = await db_manager.get_all_plays()
                plays_dict = {play['id']: play for play in (all_plays or [])}
            
            if table_name in ["Постановки", "Спектакли", "Репетиции"]:
                all_directors = await db_manager.get_all_directors()
                directors_dict = {director['id']: director for director in (all_directors or [])}
                all_locations = await db_manager.get_all_locations()
                locations_dict = {location['id']: location for location in (all_locations or [])}
                all_productions = await db_manager.get_all_productions()
                productions_dict = {production['id']: production for production in (all_productions or [])}
            
            # Преобразуем результаты в формат grid
            for result in results:
                if table_name == "Актеры":
                    data.append([result['id'], result['full_name'], result['experience']])
                elif table_name == "Авторы":
                    data.append([result['id'], result['full_name'], result['biography']])
                elif table_name == "Режиссеры":
                    data.append([result['id'], result['full_name'], result['biography']])
                elif table_name == "Пьесы":
                    data.append([result['id'], result['title'], result['genre'], result['year_written'], result['description']])
                elif table_name == "Постановки":
                    data.append([
                        result['id'], result['title'], format_date_for_display(result['production_date']),
                        result['description'],
                        plays_dict.get(result['play_id'], {}).get('title', 'Неизвестно') if result.get('play_id') else '',
                        directors_dict.get(result['director_id'], {}).get('full_name', 'Неизвестно') if result.get('director_id') else ''
                    ])
                elif table_name == "Спектакли":
                    loc = locations_dict.get(result['location_id'], {}) if result.get('location_id') else {}
                    loc_name = f"{loc.get('theatre_name', '')}, {loc.get('hall_name', '')}" if loc else 'Неизвестно'
                    data.append([
                        result['id'], format_datetime_for_display(result['datetime']),
                        loc_name,
                        productions_dict.get(result['production_id'], {}).get('title', 'Неизвестно') if result.get('production_id') else ''
                    ])
                elif table_name == "Репетиции":
                    loc = locations_dict.get(result['location_id'], {}) if result.get('location_id') else {}
                    loc_name = f"{loc.get('theatre_name', '')}, {loc.get('hall_name', '')}" if loc else 'Неизвестно'
                    data.append([
                        result['id'], format_datetime_for_display(result['datetime']),
                        loc_name,
                        productions_dict.get(result['production_id'], {}).get('title', 'Неизвестно') if result.get('production_id') else ''
                    ])
                elif table_name == "Роли":
                    data.append([
                        result['id'], result['title'], result['description'],
                        plays_dict.get(result['play_id'], {}).get('title', 'Неизвестно') if result.get('play_id') else ''
                    ])
                elif table_name == "Локации":
                    data.append([
                        result['id'], f"{result.get('theatre_name', '')}, {result.get('hall_name', '')}",
                        result.get('city') or '', result.get('street') or '',
                        result.get('house_number') or '', result.get('postal_code') or '',
                        result.get('capacity') or ''
                    ])
                elif table_name == "Театры":
                    data.append([
                        result['id'], result['name'],
                        result.get('city') or '', result.get('street') or '',
                        result.get('house_number') or '', result.get('postal_code') or ''
                    ])
            
            return data
            
            # Запускаем поиск в БД
            run_async(search_in_db())
        
        def on_search(event):
            """Обработчик поиска"""
            search_text = search_ctrl.GetValue()
            apply_search(search_text)
            event.Skip()
        
        def on_search_cancel(event):
            """Обработчик отмены поиска"""
            search_ctrl.SetValue("")
            apply_search("")
            event.Skip()
        
        search_ctrl.Bind(wx.EVT_TEXT, on_search)
        search_ctrl.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, on_search)
        search_ctrl.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, on_search_cancel)
        
        def on_column_header_click(event):
            """Обработчик клика по заголовку колонки для сортировки через aiomysql"""
            col = event.GetCol()
            if col < 0:
                return
            
            nonlocal sort_column, sort_ascending
            
            # Если кликнули по той же колонке - меняем направление сортировки
            if col == sort_column:
                sort_ascending = not sort_ascending
            else:
                sort_column = col
                sort_ascending = True
            
            # Выполняем сортировку через aiomysql, применяя текущий поисковый фильтр
            try:
                current_search = search_ctrl.GetValue()
                apply_search(current_search, sort_col=col, sort_asc=sort_ascending)
            except Exception as e:
                logging.error(f"Ошибка сортировки через aiomysql: {e}")
            
            event.Skip()
        
        # Обработчик клика по заголовку - различает колонки и строки
        def on_label_click(event):
            """Обработчик клика по заголовку - различает колонки и строки"""
            row = event.GetRow()
            col = event.GetCol()
            
            # Если клик по номеру строки (row >= 0, col < 0)
            if row >= 0 and col < 0:
                if row < grid.GetNumberRows():
                    grid.SelectRow(row)
                event.Skip()
                return
            
            # Если клик по заголовку колонки (col >= 0, row < 0)
            if col >= 0 and row < 0:
                on_column_header_click(event)
                return
            
            event.Skip()
        
        # Обработчик двойного клика по номеру строки - открывает просмотр
        def on_row_label_double_click(event):
            """Обработчик двойного клика по номеру строки - открывает просмотр"""
            row = event.GetRow()
            col = event.GetCol()
            # Проверяем что это клик по номеру строки
            if row >= 0 and col < 0:
                if row < grid.GetNumberRows():
                    grid.SelectRow(row)
                    on_view(event)
            event.Skip()
        
        grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, on_label_click)
        grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, on_row_label_double_click)
        
        
        def safe_grid_update(data, headers):
            """Обновляет grid с новыми данными из БД"""
            def do_update():
                try:
                    if not grid:
                        logging.error(f"Grid не найден для таблицы {table_name}")
                        return
                        
                    # Не логируем обновление grid (слишком часто)
                    
                    nonlocal original_data, original_headers, sort_column, sort_ascending
                    
                    original_visible = grid.IsShown()
                    grid.Hide()
                    
                    current_rows = grid.GetNumberRows()
                    current_cols = grid.GetNumberCols()
                    
                    grid.ClearGrid()
                    
                    if current_rows > 0:
                        grid.DeleteRows(0, current_rows)
                    if current_cols > 0:
                        grid.DeleteCols(0, current_cols)
                    
                    grid.ForceRefresh()
                    
                    # Не логируем очистку grid (слишком часто)
                    
                    original_data = []
                    original_headers = []
                    
                    if data:
                        original_data = [row[:] for row in data]
                    if headers:
                        original_headers = headers[:]
                    
                    # Не логируем загрузку данных в память (слишком часто)
                    
                    
                    display_data = original_data[:] if original_data else []
                    
                    if headers and len(headers) > 0:
                        grid.AppendCols(len(headers))
                        if len(display_data) > 0:
                            grid.AppendRows(len(display_data))
                        
                        for i, header in enumerate(headers):
                            header_text = str(header)
                            if i == sort_column:
                                header_text += " ▲" if sort_ascending else " ▼"
                            grid.SetColLabelValue(i, header_text)
                        
                        if len(display_data) > 0:
                            for i, row in enumerate(display_data):
                                for j, value in enumerate(row):
                                    if j < len(headers):
                                        cell_value = str(value) if value is not None else ""
                                        grid.SetCellValue(i, j, cell_value)
                        
                        grid.AutoSizeColumns()
                    
                    if original_visible:
                        grid.Show()
                    
                    grid.ClearSelection()
                    grid.ForceRefresh()
                    grid.Refresh()
                    grid.Update()
                    grid.AutoSizeColumns()
                    
                    panel.Layout()
                    panel.Refresh()
                    panel.Update()
                    
                    frame = panel.GetTopLevelParent()
                    if frame:
                        frame.Layout()
                        frame.Refresh()
                        frame.Update()
                    
                    # Не логируем обновление grid (слишком часто)
                    
                except Exception as e:
                    logging.error(f"Ошибка обновления grid {table_name}: {e}", exc_info=True)
            
            if wx.IsMainThread():
                do_update()
            else:
                wx.CallAfter(do_update)

        async def load_data():
            try:
                # Не логируем загрузку данных (слишком часто)
                
                # Получаем данные через get_sample_data, который уже должен быть исправлен для сортировки
                tables_data, table_headers = await get_sample_data(force_refresh=True)
                data = tables_data.get(table_name, [])
                headers = table_headers.get(table_name, [])
                
                # Не логируем количество полученных записей (слишком часто)
                
                # Обновляем grid
                safe_grid_update(data, headers)
                
            except Exception as e:
                logging.error(f"Ошибка загрузки данных для таблицы {table_name}: {e}")
                safe_grid_update([], [])
        
        future = run_async(load_data())
        if not future:
            logging.error(f"Не удалось запустить загрузку данных для таблицы {table_name}")
            safe_grid_update([], [])

        control_panel = wx.Panel(panel)
        control_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        def refresh_data():
            """Обновление данных таблицы из БД - ПРИНУДИТЕЛЬНАЯ перезагрузка"""
            # Не логируем принудительное обновление (слишком часто)
            
            current_search = search_ctrl.GetValue()
            saved_sort_column = sort_column
            saved_sort_ascending = sort_ascending
            
            async def reload():
                try:
                    nonlocal original_data, original_headers, sort_column, sort_ascending
                    
                    # ПРИНУДИТЕЛЬНО очищаем кэш перед загрузкой
                    original_data = []
                    original_headers = []
                    
                    # ПРИНУДИТЕЛЬНО загружаем СВЕЖИЕ данные из БД (без кэша)
                    # Не логируем запрос свежих данных (слишком часто)
                    # Небольшая задержка для гарантии, что БД обработала изменения
                    await asyncio.sleep(0.2)
                    tables_data, table_headers = await get_sample_data(force_refresh=True)
                    
                    if table_name not in tables_data:
                        logging.error(f"Таблица {table_name} не найдена")
                        return False
                    
                    data = tables_data.get(table_name, [])
                    headers = table_headers.get(table_name, [])
                    
                    # Не логируем получение свежих записей (слишком часто)
                    
                    def update_grid():
                        nonlocal original_data, original_headers, sort_column, sort_ascending
                        # ПРИНУДИТЕЛЬНО очищаем старые данные
                        original_data = []
                        original_headers = []
                        # Устанавливаем новые данные
                        if data:
                            original_data = [row[:] for row in data]
                        if headers:
                            original_headers = headers[:]
                        sort_column = saved_sort_column
                        sort_ascending = saved_sort_ascending
                        # Обновляем grid с новыми данными
                        safe_grid_update(data, headers)
                        if current_search:
                            search_ctrl.SetValue(current_search)
                            apply_search(current_search)
                        # Не логируем обновление grid (слишком часто)
                        
                        # Принудительное обновление интерфейса
                        if grid:
                            grid.ClearSelection()
                            grid.ForceRefresh()
                            grid.Refresh()
                            grid.Update()
                            grid.AutoSizeColumns()
                        if panel:
                            panel.Layout()
                            panel.Refresh()
                            panel.Update()
                        frame = panel.GetTopLevelParent() if panel else None
                        if frame:
                            frame.Layout()
                            frame.Refresh()
                            frame.Update()
                    
                    wx.CallAfter(update_grid)
                    return True
                except Exception as e:
                    logging.error(f"Ошибка обновления таблицы {table_name}: {e}", exc_info=True)
                    return False
            
            def on_reload_complete(success):
                def do_complete():
                    if success:
                        try:
                            new_rows = grid.GetNumberRows() if grid else 0
                            # Не логируем обновление данных таблицы (слишком часто)
                            
                            def delayed_refresh():
                                try:
                                    final_rows = grid.GetNumberRows() if grid else 0
                                    # Не логируем финальную проверку grid (слишком часто)
                                    
                                    if grid:
                                        grid.ForceRefresh()
                                        grid.Refresh()
                                        grid.Update()
                                        grid.ClearSelection()
                                        grid.SetFocus()
                                        grid.Refresh()
                                        
                                    if panel:
                                        panel.Refresh()
                                        panel.Update()
                                    
                                    frame = panel.GetTopLevelParent() if panel else None
                                    if frame:
                                        frame.Refresh()
                                        frame.Update()
                                        
                                except Exception as e:
                                    logging.error(f"Ошибка delayed_refresh: {e}", exc_info=True)
                            
                            delayed_refresh()
                            
                            def delayed_refresh_1():
                                delayed_refresh()
                            
                            def delayed_refresh_2():
                                delayed_refresh()
                            
                            wx.CallAfter(delayed_refresh_1)
                            if wx.IsMainThread():
                                wx.CallLater(200, delayed_refresh_2)
                            else:
                                wx.CallAfter(delayed_refresh_2)
                            
                        except Exception as e:
                            logging.error(f"Ошибка в on_reload_complete: {e}", exc_info=True)
                    else:
                        logging.error(f"ОШИБКА: Данные таблицы {table_name} НЕ обновлены из БД")
                
                if wx.IsMainThread():
                    do_complete()
                else:
                    wx.CallAfter(do_complete)
            
            future = run_async(reload())
            if future:
                future.add_done_callback(lambda f: on_reload_complete(f.result() if not f.exception() else False))
                return True
            else:
                logging.error(f"Не удалось запустить обновление таблицы {table_name}")
                return False
        
        panel.refresh_data = refresh_data
        
        def refresh_table_and_dashboard():
            """Универсальная функция для обновления текущей таблицы и дашборда после CRUD операций"""
            # Не логируем обновление после CRUD (слишком часто)
            # Сначала обновляем текущую таблицу (локальная функция refresh_data)
            # Она загрузит СВЕЖИЕ данные из БД
            # Не логируем вызов refresh_data (слишком часто)
            refresh_data()
            # Затем обновляем общие данные для дашборда (с небольшой задержкой)
            def refresh_dashboard_delayed():
                # Не логируем обновление дашборда (слишком часто)
                refresh_after_crud()
            wx.CallLater(300, refresh_dashboard_delayed)

        def on_add(event):
            try:
                if not db_initialized:
                    show_error("База данных не инициализирована")
                    return
                    
                if table_name == "Актеры":
                    dialog = EditActorDialog(panel, "Добавить актера")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        
                        async def add_actor_with_connections():
                            try:
                                actor_id = await db_manager.add_actor(new_data['full_name'], new_data['experience'])
                                if not actor_id:
                                    raise Exception("Не удалось создать актера, ID не получен.")
                                
                                # Сохраняем роли
                                for role_data in new_data.get('roles_data', []):
                                    await db_manager.add_actor_role(actor_id, role_data['role_id'], role_data['production_id'])
                                
                                # Сохраняем репетиции
                                for reh_id in new_data.get('rehearsal_ids', []):
                                    await db_manager.add_actor_to_rehearsal(actor_id, reh_id)
                                
                                # Сохраняем постановки
                                for prod_id in new_data.get('production_ids', []):
                                    await db_manager.add_actor_to_production(actor_id, prod_id)
                                
                                return True, new_data['full_name']
                            except Exception as e:
                                logging.error(f"Ошибка при добавлении актера с связями: {e}")
                                raise e
                        
                        future = run_async(add_actor_with_connections())
                        if future:
                            try:
                                success, name = future.result(timeout=10)
                                if success:
                                    show_success(f"Актер {name} успешно добавлен")
                                    log_action(f"Добавлен актер: {name}")
                                    refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Авторы":
                    dialog = EditAuthorDialog(panel, "Добавить автора")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        future = run_async(db_manager.add_author(new_data['full_name'], new_data['biography']))
                        if future:
                            try:
                                future.result(timeout=10)
                                show_success(f"Автор {new_data['full_name']} успешно добавлен")
                                log_action(f"Добавлен автор: {new_data['full_name']}")
                                refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Режиссеры":
                    dialog = EditDirectorDialog(panel, "Добавить режиссера")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        future = run_async(db_manager.add_director(new_data['full_name'], new_data['biography']))
                        if future:
                            try:
                                future.result(timeout=10)
                                show_success(f"Режиссер {new_data['full_name']} успешно добавлен")
                                log_action(f"Добавлен режиссер: {new_data['full_name']}")
                                refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Пьесы":
                    dialog = EditPlayDialog(panel, "Добавить пьесу")
                    if dialog.ShowModal() == wx.ID_OK:
                        play_data, author_ids = dialog.get_data()

                        async def add_play_with_authors():
                            new_play_id = None
                            try:
                                new_play_id = await db_manager.add_play(
                                    play_data['title'], play_data['genre'], 
                                    play_data['year_written'], play_data['description']
                                )
                                if not new_play_id:
                                    raise Exception("Не удалось создать пьесу, ID не получен.")

                                await db_manager.set_play_authors(new_play_id, author_ids)
                                return True, play_data['title']
                            except Exception as e:
                                if new_play_id:
                                    await db_manager.delete_play(new_play_id)
                                logging.error(f"Ошибка при добавлении пьесы с авторами: {e}")
                                raise e

                        future = run_async(add_play_with_authors())
                        if future:
                            try:
                                success, title = future.result(timeout=10)
                                if success:
                                    show_success(f"Пьеса {title} успешно добавлена")
                                    log_action(f"Добавлена пьеса: {title}")
                                    refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Постановки":
                    dialog = EditProductionDialog(panel, "Добавить постановку")
                    if dialog.ShowModal() == wx.ID_OK:
                        production_data, cast_data = dialog.get_data()

                        async def add_production_with_cast():
                            new_production_id = None
                            try:
                                # 1. Добавляем постановку
                                new_production_id = await db_manager.add_production(
                                    production_data['title'], production_data['production_date'], 
                                    production_data['description'], production_data['play_id'], production_data['director_id']
                                )

                                if not new_production_id:
                                    raise Exception("Не удалось создать постановку, ID не получен.")

                                # 2. Добавляем состав
                                if cast_data:
                                    # Обновляем cast_data, добавляя production_id (хотя set_production_cast и так его примет)
                                    await db_manager.set_production_cast(new_production_id, cast_data)

                                return True, production_data['title']
                            except Exception as e:
                                # Попытка откатить, если постановка создалась, а состав - нет
                                if new_production_id:
                                    await db_manager.delete_production(new_production_id)
                                logging.error(f"Ошибка при добавлении постановки с составом: {e}")
                                raise e # Передаем ошибку дальше

                        future = run_async(add_production_with_cast())
                        if future:
                            try:
                                success, title = future.result(timeout=10)
                                if success:
                                    show_success(f"Постановка {title} с составом успешно добавлена")
                                    log_action(f"Добавлена постановка: {title}")
                                    refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Спектакли":
                    dialog = EditPerformanceDialog(panel, "Добавить спектакль")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        future = run_async(db_manager.add_performance(
                            new_data['datetime'], new_data['location_id'], new_data['production_id']
                        ))
                        if future:
                            try:
                                future.result(timeout=10)
                                show_success(f"Спектакль успешно добавлен")
                                log_action(f"Добавлен спектакль")
                                refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Репетиции":
                    dialog = EditRehearsalDialog(panel, "Добавить репетицию")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        
                        async def add_rehearsal_with_actors():
                            try:
                                rehearsal_id = await db_manager.add_rehearsal(
                                    new_data['datetime'], new_data['location_id'], new_data['production_id']
                                )
                                if new_data.get('actor_ids'):
                                    await db_manager.set_rehearsal_actors(rehearsal_id, new_data['actor_ids'])
                                return True
                            except Exception as e:
                                logging.error(f"Ошибка при добавлении репетиции с актерами: {e}")
                                raise e
                        
                        future = run_async(add_rehearsal_with_actors())
                        if future:
                            try:
                                future.result(timeout=10)
                                show_success(f"Репетиция успешно добавлена")
                                log_action(f"Добавлена репетиция")
                                refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Роли":
                    dialog = EditRoleDialog(panel, "Добавить роль")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        future = run_async(db_manager.add_role(
                            new_data['title'], new_data['description'], new_data['play_id']
                        ))
                        if future:
                            try:
                                future.result(timeout=10)
                                show_success(f"Роль {new_data['title']} успешно добавлена")
                                log_action(f"Добавлена роль: {new_data['title']}")
                                refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                elif table_name == "Локации":
                    dialog = EditLocationDialog(panel, "Добавить зал/сцену")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        future = run_async(db_manager.add_location(
                            new_data['theatre_id'], new_data['hall_name'],
                            new_data.get('capacity')
                        ))
                        if future:
                            try:
                                future.result(timeout=10)
                                show_success(f"Зал/сцена {new_data['hall_name']} успешно добавлен(а)")
                                log_action(f"Добавлен зал/сцена: {new_data['hall_name']}")
                                refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
                
                elif table_name == "Театры":
                    dialog = EditTheatreDialog(panel, "Добавить театр")
                    if dialog.ShowModal() == wx.ID_OK:
                        new_data = dialog.get_data()
                        future = run_async(db_manager.add_theatre(
                            new_data['name'], new_data.get('city'),
                            new_data.get('street'), new_data.get('house_number'),
                            new_data.get('postal_code')
                        ))
                        if future:
                            try:
                                future.result(timeout=10)
                                show_success(f"Театр {new_data['name']} успешно добавлен")
                                log_action(f"Добавлен театр: {new_data['name']}")
                                refresh_table_and_dashboard()
                            except Exception as e:
                                show_error(f"Ошибка при добавлении: {str(e)}")
            
            except Exception as e:
                show_error(f"Ошибка при добавлении: {str(e)}")
                log_action(f"Ошибка добавления в таблицу {table_name}: {str(e)}", logging.ERROR)
        
        def on_edit(event):
            try:
                if not db_initialized:
                    show_error("База данных не инициализирована")
                    return
                    
                selected_rows = grid.GetSelectedRows()
                if not selected_rows:
                    show_error("Выберите запись для редактирования")
                    return
                    
                row_idx = selected_rows[0]
                if row_idx >= grid.GetNumberRows():
                    show_error("Неверный индекс строки")
                    return
                    
                record_id = int(grid.GetCellValue(row_idx, 0))
                
                if table_name == "Актеры":
                    future = run_async(db_manager.get_actor_by_id(record_id))
                    if future:
                        actor_data = future.result(timeout=10)
                        if actor_data:
                            dialog = EditActorDialog(panel, "Редактировать актера", actor_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                
                                async def update_actor_with_connections():
                                    try:
                                        # Обновляем основные данные
                                        await db_manager.update_actor(
                                            record_id, updated_data['full_name'], updated_data['experience']
                                        )
                                        
                                        # Получаем текущие связи
                                        current_roles = await db_manager.get_actor_roles(record_id)
                                        current_rehearsals = await db_manager.get_actor_rehearsals(record_id)
                                        current_productions = await db_manager.get_actor_productions(record_id)
                                        
                                        # Удаляем старые роли
                                        for role in current_roles:
                                            await db_manager.remove_actor_role(
                                                record_id, role['role_id'], role['production_id']
                                            )
                                        
                                        # Добавляем новые роли
                                        for role_data in updated_data.get('roles_data', []):
                                            await db_manager.add_actor_role(
                                                record_id, role_data['role_id'], role_data['production_id']
                                            )
                                        
                                        # Обновляем репетиции - удаляем старые
                                        for reh in current_rehearsals:
                                            await db_manager.remove_actor_from_rehearsal(record_id, reh['rehearsal_id'])
                                        
                                        # Добавляем новые репетиции
                                        for reh_id in updated_data.get('rehearsal_ids', []):
                                            await db_manager.add_actor_to_rehearsal(record_id, reh_id)
                                        
                                        # Удаляем старые постановки
                                        for prod in current_productions:
                                            await db_manager.remove_actor_from_production(record_id, prod['production_id'])
                                        
                                        # Добавляем новые постановки
                                        for prod_id in updated_data.get('production_ids', []):
                                            await db_manager.add_actor_to_production(record_id, prod_id)
                                        
                                        return True, updated_data['full_name']
                                    except Exception as e:
                                        logging.error(f"Ошибка при обновлении актера с связями: {e}")
                                        raise e
                                
                                future = run_async(update_actor_with_connections())
                                if future:
                                    try:
                                        success, name = future.result(timeout=10)
                                        if success:
                                            show_success(f"Актер {name} успешно обновлен")
                                            log_action(f"Обновлен актер: {name}")
                                            refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Авторы":
                    future = run_async(db_manager.get_author_by_id(record_id))
                    if future:
                        author_data = future.result(timeout=10)
                        if author_data:
                            dialog = EditAuthorDialog(panel, "Редактировать автора", author_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                future = run_async(db_manager.update_author(
                                    record_id, updated_data['full_name'], updated_data['biography']
                                ))
                                if future:
                                    try:
                                        future.result(timeout=10)
                                        show_success(f"Автор {updated_data['full_name']} успешно обновлен")
                                        log_action(f"Обновлен автор: {updated_data['full_name']}")
                                        refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Режиссеры":
                    future = run_async(db_manager.get_director_by_id(record_id))
                    if future:
                        director_data = future.result(timeout=10)
                        if director_data:
                            dialog = EditDirectorDialog(panel, "Редактировать режиссера", director_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                future = run_async(db_manager.update_director(
                                    record_id, updated_data['full_name'], updated_data['biography']
                                ))
                                if future:
                                    try:
                                        future.result(timeout=10)
                                        show_success(f"Режиссер {updated_data['full_name']} успешно обновлен")
                                        log_action(f"Обновлен режиссер: {updated_data['full_name']}")
                                        refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Пьесы":
                    future = run_async(db_manager.get_play_by_id(record_id))
                    if future:
                        play_data = future.result(timeout=10)
                        if play_data:
                            play_data['id'] = record_id # Добавляем ID для загрузки авторов
                            dialog = EditPlayDialog(panel, "Редактировать пьесу", play_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data, updated_author_ids = dialog.get_data()

                                async def update_play_with_authors():
                                    try:
                                        await db_manager.update_play(
                                            record_id, updated_data['title'], updated_data['genre'], 
                                            updated_data['year_written'], updated_data['description']
                                        )
                                        await db_manager.set_play_authors(record_id, updated_author_ids)
                                        return True, updated_data['title']
                                    except Exception as e:
                                        logging.error(f"Ошибка при обновлении пьесы с авторами: {e}")
                                        raise e

                                future_update = run_async(update_play_with_authors())
                                if future_update:
                                    try:
                                        success, title = future_update.result(timeout=10)
                                        if success:
                                            show_success(f"Пьеса {title} успешно обновлена")
                                            log_action(f"Обновлена пьеса: {title}")
                                            refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Постановки":
                    future = run_async(db_manager.get_production_by_id(record_id))
                    if future:
                        production_data = future.result(timeout=10)
                        if production_data:
                            # Передаем 'id' постановки, он нужен для загрузки состава
                            production_data['id'] = record_id 
                            dialog = EditProductionDialog(panel, "Редактировать постановку", production_data)

                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data, updated_cast = dialog.get_data()

                                async def update_production_with_cast():
                                    try:
                                        # 1. Обновляем основную информацию
                                        await db_manager.update_production(
                                            record_id, updated_data['title'], updated_data['production_date'], 
                                            updated_data['description'], updated_data['play_id'], updated_data['director_id']
                                        )

                                        # 2. Обновляем состав
                                        await db_manager.set_production_cast(record_id, updated_cast)

                                        return True, updated_data['title']
                                    except Exception as e:
                                        logging.error(f"Ошибка при обновлении постановки с составом: {e}")
                                        raise e

                                future_update = run_async(update_production_with_cast())
                                if future_update:
                                    try:
                                        success, title = future_update.result(timeout=10)
                                        if success:
                                            show_success(f"Постановка {title} успешно обновлена")
                                            log_action(f"Обновлена постановка: {title}")
                                            refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Спектакли":
                    future = run_async(db_manager.get_performance_by_id(record_id))
                    if future:
                        performance_data = future.result(timeout=10)
                        if performance_data:
                            dialog = EditPerformanceDialog(panel, "Редактировать спектакль", performance_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                future = run_async(db_manager.update_performance(
                                    record_id, updated_data['datetime'], updated_data['location_id'], updated_data['production_id']
                                ))
                                if future:
                                    try:
                                        future.result(timeout=10)
                                        show_success(f"Спектакль успешно обновлен")
                                        log_action(f"Обновлен спектакль")
                                        refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Репетиции":
                    future = run_async(db_manager.get_rehearsal_by_id(record_id))
                    if future:
                        rehearsal_data = future.result(timeout=10)
                        if rehearsal_data:
                            rehearsal_data['id'] = record_id
                            dialog = EditRehearsalDialog(panel, "Редактировать репетицию", rehearsal_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                
                                async def update_rehearsal_with_actors():
                                    try:
                                        await db_manager.update_rehearsal(
                                            record_id, updated_data['datetime'], updated_data['location_id'], updated_data['production_id']
                                        )
                                        if 'actor_ids' in updated_data:
                                            await db_manager.set_rehearsal_actors(record_id, updated_data['actor_ids'])
                                        return True
                                    except Exception as e:
                                        logging.error(f"Ошибка при обновлении репетиции с актерами: {e}")
                                        raise e
                                
                                future_update = run_async(update_rehearsal_with_actors())
                                if future_update:
                                    try:
                                        future_update.result(timeout=10)
                                        show_success(f"Репетиция успешно обновлена")
                                        log_action(f"Обновлена репетиция")
                                        refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Роли":
                    future = run_async(db_manager.get_role_by_id(record_id))
                    if future:
                        role_data = future.result(timeout=10)
                        if role_data:
                            dialog = EditRoleDialog(panel, "Редактировать роль", role_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                future = run_async(db_manager.update_role(
                                    record_id, updated_data['title'], updated_data['description'], updated_data['play_id']
                                ))
                                if future:
                                    try:
                                        future.result(timeout=10)
                                        show_success(f"Роль {updated_data['title']} успешно обновлена")
                                        log_action(f"Обновлена роль: {updated_data['title']}")
                                        refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                elif table_name == "Локации":
                    future = run_async(db_manager.get_location_by_id(record_id))
                    if future:
                        location_data = future.result(timeout=10)
                        if location_data:
                            dialog = EditLocationDialog(panel, "Редактировать локацию", location_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                future = run_async(db_manager.update_location(
                                    record_id, updated_data['theatre_id'], updated_data['hall_name'],
                                    updated_data.get('capacity')
                                ))
                                if future:
                                    try:
                                        future.result(timeout=10)
                                        show_success(f"Зал/сцена {updated_data['hall_name']} успешно обновлен(а)")
                                        log_action(f"Обновлен зал/сцена: {updated_data['hall_name']}")
                                        refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")
                
                elif table_name == "Театры":
                    future = run_async(db_manager.get_theatre_by_id(record_id))
                    if future:
                        theatre_data = future.result(timeout=10)
                        if theatre_data:
                            dialog = EditTheatreDialog(panel, "Редактировать театр", theatre_data)
                            if dialog.ShowModal() == wx.ID_OK:
                                updated_data = dialog.get_data()
                                future = run_async(db_manager.update_theatre(
                                    record_id, updated_data['name'], updated_data.get('city'),
                                    updated_data.get('street'), updated_data.get('house_number'),
                                    updated_data.get('postal_code')
                                ))
                                if future:
                                    try:
                                        future.result(timeout=10)
                                        show_success(f"Театр {updated_data['name']} успешно обновлен")
                                        log_action(f"Обновлен театр: {updated_data['name']}")
                                        refresh_table_and_dashboard()
                                    except Exception as e:
                                        show_error(f"Ошибка при обновлении: {str(e)}")

            except Exception as e:
                show_error(f"Ошибка при редактировании: {str(e)}")
                log_action(f"Ошибка редактирования в таблице {table_name}: {str(e)}", logging.ERROR)
        
        def on_view(event):
            try:
                selected_rows = grid.GetSelectedRows()
                if not selected_rows:
                    show_error("Выберите запись для просмотра")
                    return
                    
                row_idx = selected_rows[0]
                if row_idx >= grid.GetNumberRows():
                    show_error("Неверный индекс строки")
                    return
                    
                record_id = int(grid.GetCellValue(row_idx, 0))
                
                if table_name == "Актеры":
                    future = run_async(db_manager.get_actor_by_id(record_id))
                    if future:
                        actor_data = future.result(timeout=10)
                        if actor_data:
                            dialog = ViewActorDialog(panel, "Просмотр актера", actor_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр актера: {actor_data['full_name']}")
                
                elif table_name == "Авторы":
                    future = run_async(db_manager.get_author_by_id(record_id))
                    if future:
                        author_data = future.result(timeout=10)
                        if author_data:
                            dialog = ViewAuthorDialog(panel, "Просмотр автора", author_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр автора: {author_data['full_name']}")
                
                elif table_name == "Режиссеры":
                    future = run_async(db_manager.get_director_by_id(record_id))
                    if future:
                        director_data = future.result(timeout=10)
                        if director_data:
                            dialog = ViewDirectorDialog(panel, "Просмотр режиссера", director_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр режиссера: {director_data['full_name']}")
                
                elif table_name == "Пьесы":
                    future = run_async(db_manager.get_play_by_id(record_id))
                    if future:
                        play_data = future.result(timeout=10)
                        if play_data:
                            dialog = ViewPlayDialog(panel, "Просмотр пьесы", play_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр пьесы: {play_data['title']}")
                
                elif table_name == "Постановки":
                    future = run_async(db_manager.get_production_by_id(record_id))
                    if future:
                        production_data = future.result(timeout=10)
                        if production_data:
                            dialog = ViewProductionDialog(panel, "Просмотр постановки", production_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр постановки: {production_data['title']}")
                
                elif table_name == "Спектакли":
                    future = run_async(db_manager.get_performance_by_id(record_id))
                    if future:
                        performance_data = future.result(timeout=10)
                        if performance_data:
                            dialog = ViewPerformanceDialog(panel, "Просмотр спектакля", performance_data)
                            dialog.ShowModal()
                            log_action("Просмотр спектакля")
                
                elif table_name == "Репетиции":
                    future = run_async(db_manager.get_rehearsal_by_id(record_id))
                    if future:
                        rehearsal_data = future.result(timeout=10)
                        if rehearsal_data:
                            dialog = ViewRehearsalDialog(panel, "Просмотр репетиции", rehearsal_data)
                            dialog.ShowModal()
                            log_action("Просмотр репетиции")
                
                elif table_name == "Роли":
                    future = run_async(db_manager.get_role_by_id(record_id))
                    if future:
                        role_data = future.result(timeout=10)
                        if role_data:
                            dialog = ViewRoleDialog(panel, "Просмотр роли", role_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр роли: {role_data['title']}")
                elif table_name == "Локации":
                    future = run_async(db_manager.get_location_by_id(record_id))
                    if future:
                        location_data = future.result(timeout=10)
                        if location_data:
                            dialog = ViewLocationDialog(panel, "Просмотр локации", location_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр локации: {location_data.get('theatre_name', '')}, {location_data.get('hall_name', '')}")
                
                elif table_name == "Театры":
                    future = run_async(db_manager.get_theatre_by_id(record_id))
                    if future:
                        theatre_data = future.result(timeout=10)
                        if theatre_data:
                            dialog = ViewTheatreDialog(panel, "Просмотр театра", theatre_data)
                            dialog.ShowModal()
                            log_action(f"Просмотр театра: {theatre_data['name']}")

            
            except Exception as e:
                show_error(f"Ошибка при просмотре: {str(e)}")
                log_action(f"Ошибка просмотра в таблице {table_name}: {str(e)}", logging.ERROR)
        
        def on_delete(event):
            try:
                if not db_initialized:
                    show_error("База данных не инициализирована")
                    return
                    
                selected_rows = grid.GetSelectedRows()
                if not selected_rows:
                    show_error("Выберите запись для удаления")
                    return
                    
                row_idx = selected_rows[0]
                if row_idx >= grid.GetNumberRows():
                    show_error("Неверный индекс строки")
                    return
                    
                record_id = int(grid.GetCellValue(row_idx, 0))
                record_name = grid.GetCellValue(row_idx, 1)
                
                if show_confirmation(f"Вы уверены, что хотите удалить запись '{record_name}'?"):
                    try:
                        if table_name == "Актеры":
                            future = run_async(db_manager.delete_actor(record_id))
                        elif table_name == "Авторы":
                            future = run_async(db_manager.delete_author(record_id))
                        elif table_name == "Режиссеры":
                            future = run_async(db_manager.delete_director(record_id))
                        elif table_name == "Пьесы":
                            future = run_async(db_manager.delete_play(record_id))
                        elif table_name == "Постановки":
                            future = run_async(db_manager.delete_production(record_id))
                        elif table_name == "Спектакли":
                            future = run_async(db_manager.delete_performance(record_id))
                        elif table_name == "Репетиции":
                            future = run_async(db_manager.delete_rehearsal(record_id))
                        elif table_name == "Роли":
                            future = run_async(db_manager.delete_role(record_id))
                        elif table_name == "Локации":
                            future = run_async(db_manager.delete_location(record_id))
                        elif table_name == "Театры":
                            future = run_async(db_manager.delete_theatre(record_id))
                        
                        if future:
                            try:
                                # Ждем завершения операции удаления
                                delete_result = future.result(timeout=10)
                                # Не логируем завершение удаления (слишком часто)
                                
                                show_success(f"Запись '{record_name}' успешно удалена")
                                log_action(f"Удаление записи из таблицы {table_name}: {record_name}")
                                
                                async def refresh_after_delete():
                                    try:
                                        await asyncio.sleep(0.3)
                                        await refresh_all_data()
                                        await asyncio.sleep(0.2)
                                        tables_data, table_headers = await get_sample_data(force_refresh=True)
                                        return tables_data, table_headers
                                    except Exception as e:
                                        logging.error(f"Ошибка обновления после удаления: {e}", exc_info=True)
                                        return None, None
                                
                                def on_delete_complete(future_result):
                                    try:
                                        result = future_result.result(timeout=15) if future_result else (None, None)
                                        tables_data_new, table_headers_new = result
                                        
                                        def update_after_delete():
                                            nonlocal original_data, original_headers
                                            original_data = []
                                            original_headers = []
                                            
                                            if tables_data_new and table_headers_new:
                                                data = tables_data_new.get(table_name, [])
                                                headers = table_headers_new.get(table_name, [])
                                                
                                                if data:
                                                    original_data = [row[:] for row in data]
                                                if headers:
                                                    original_headers = headers[:]
                                                
                                                safe_grid_update(data, headers)
                                                # Не логируем обновление после удаления (слишком часто)
                                            
                                            refresh_table_and_dashboard()
                                        
                                        wx.CallAfter(update_after_delete)
                                    except Exception as e:
                                        logging.error(f"Ошибка обработки результата: {e}", exc_info=True)
                                        wx.CallAfter(refresh_table_and_dashboard)
                                
                                refresh_future = run_async(refresh_after_delete())
                                if refresh_future:
                                    refresh_future.add_done_callback(lambda f: on_delete_complete(f))
                                else:
                                    wx.CallLater(500, refresh_table_and_dashboard)
                                
                            except Exception as e:
                                error_msg = str(e)
                                if "foreign key constraint" in error_msg:
                                    show_error(f"Невозможно удалить запись '{record_name}': она связана с другими данными в системе")
                                else:
                                    show_error(f"Ошибка при удалении: {error_msg}")
                    except Exception as e:
                        show_error(f"Ошибка при удалении: {str(e)}")
            
            except Exception as e:
                show_error(f"Ошибка при удалении: {str(e)}")
                log_action(f"Ошибка удаления из таблицы {table_name}: {str(e)}", logging.ERROR)
        
        def on_double_click(event):
            row = event.GetRow()
            if row >= 0 and row < grid.GetNumberRows():
                grid.SelectRow(row)
                on_view(event)
            event.Skip()
        
        add_btn = wx.Button(control_panel, -1, "➕ Добавить")
        add_btn.SetMinSize((100, 40))
        view_btn = wx.Button(control_panel, -1, "👁️ Просмотр")
        view_btn.SetMinSize((120, 40))
        edit_btn = wx.Button(control_panel, -1, "✏️ Редактировать")
        edit_btn.SetMinSize((140, 40))
        delete_btn = wx.Button(control_panel, -1, "🗑️ Удалить")
        delete_btn.SetMinSize((120, 40))
        refresh_btn = wx.Button(control_panel, -1, "🔄 Обновить")
        refresh_btn.SetMinSize((120, 40))
        
        add_btn.Bind(wx.EVT_BUTTON, on_add)
        view_btn.Bind(wx.EVT_BUTTON, on_view)
        edit_btn.Bind(wx.EVT_BUTTON, on_edit)
        delete_btn.Bind(wx.EVT_BUTTON, on_delete)
        # Кнопка "Обновить" должна вызывать локальную функцию refresh_data с принудительным обновлением
        def on_refresh_table(event):
            """Принудительное обновление таблицы из БД"""
            # Не логируем нажатие кнопки обновить (слишком часто)
            current_search = search_ctrl.GetValue()
            saved_sort_column = sort_column
            saved_sort_ascending = sort_ascending
            
            refresh_btn = event.GetEventObject()
            original_label = refresh_btn.GetLabel()
            refresh_btn.SetLabel("⏳ Обновление...")
            refresh_btn.Disable()
            
            async def force_reload_table():
                """Принудительная перезагрузка таблицы из БД"""
                try:
                    # Не логируем принудительную перезагрузку (слишком часто)
                    
                    nonlocal original_data, original_headers
                    # ПРИНУДИТЕЛЬНО очищаем кэш перед загрузкой
                    original_data = []
                    original_headers = []
                    
                    # ПРИНУДИТЕЛЬНО загружаем СВЕЖИЕ данные из БД (без кэша)
                    # Не логируем запрос свежих данных (слишком часто)
                    # Небольшая задержка для гарантии, что БД обработала изменения
                    await asyncio.sleep(0.2)
                    tables_data, table_headers = await get_sample_data(force_refresh=True)
                    
                    data = tables_data.get(table_name, [])
                    headers = table_headers.get(table_name, [])
                    
                    # Не логируем получение свежих записей (слишком часто)
                    
                    def update_grid():
                        nonlocal original_data, original_headers, sort_column, sort_ascending
                        # ПРИНУДИТЕЛЬНО очищаем старые данные
                        original_data = []
                        original_headers = []
                        # Устанавливаем новые данные
                        if data:
                            original_data = [row[:] for row in data]
                        if headers:
                            original_headers = headers[:]
                        sort_column = saved_sort_column
                        sort_ascending = saved_sort_ascending
                        # Обновляем grid с новыми данными
                        safe_grid_update(data, headers)
                        if current_search:
                            search_ctrl.SetValue(current_search)
                            apply_search(current_search)
                        # Не логируем принудительное обновление таблицы (слишком часто)
                        
                        # Принудительное обновление интерфейса
                        if grid:
                            grid.ForceRefresh()
                            grid.Refresh()
                            grid.Update()
                            grid.ClearSelection()
                        if panel:
                            panel.Layout()
                            panel.Refresh()
                            panel.Update()
                        frame = panel.GetTopLevelParent() if panel else None
                        if frame:
                            frame.Layout()
                            frame.Refresh()
                            frame.Update()
                    
                    wx.CallAfter(update_grid)
                    return True
                except Exception as e:
                    logging.error(f"Ошибка перезагрузки таблицы: {e}", exc_info=True)
                    return False
            
            def on_complete(success):
                wx.CallAfter(refresh_btn.SetLabel, original_label)
                wx.CallAfter(refresh_btn.Enable)
                
                if success:
                    wx.CallAfter(lambda: show_success(f"Таблица {table_name} успешно обновлена"))
                    # Также обновляем дашборд
                    wx.CallAfter(refresh_table_and_dashboard)
                else:
                    wx.CallAfter(lambda: show_error("Ошибка при обновлении таблицы"))
            
            future = run_async(force_reload_table())
            if future:
                future.add_done_callback(lambda f: on_complete(f.result() if not f.exception() else False))
            else:
                on_complete(False)
                show_error("Не удалось запустить обновление таблицы")
        
        refresh_btn.Bind(wx.EVT_BUTTON, on_refresh_table)
        
        grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, on_double_click)
        
        control_sizer.Add(add_btn, 0, wx.RIGHT, 10)
        control_sizer.Add(view_btn, 0, wx.RIGHT, 10)
        control_sizer.Add(edit_btn, 0, wx.RIGHT, 10)
        control_sizer.Add(delete_btn, 0, wx.RIGHT, 10)
        control_sizer.Add(refresh_btn, 0)
        
        control_panel.SetSizer(control_sizer)
        panel_sizer.Add(control_panel, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(panel_sizer)
        return panel
        
    except Exception as e:
        logging.error(f"Ошибка создания таблицы {table_name}: {str(e)}")
        error_panel = wx.Panel(parent)
        error_sizer = wx.BoxSizer(wx.VERTICAL)
        error_text = wx.StaticText(error_panel, -1, f"Ошибка создания таблицы: {str(e)}")
        error_sizer.Add(error_text, 1, wx.ALL | wx.ALIGN_CENTER, 20)
        error_panel.SetSizer(error_sizer)
        return error_panel

class DashboardPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.line_chart_canvas = None
        self.pie_chart_canvas = None
        self.rehearsals_grid = None
        self.metrics_cards = {}
        self.quick_access_buttons = []
        self.base_font_size = 10
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.init_ui()
        wx.CallAfter(lambda: theme_manager.apply_theme(self))

    def _style_primary_button(self, button):
        """Применяет цвета текущей темы к основным кнопкам."""
        theme = theme_manager.get_theme()
        button.SetBackgroundColour(theme['button_bg'])
        button.SetForegroundColour(theme['button_fg'])
        button.SetOwnBackgroundColour(theme['button_bg'])

    def _style_panel(self, panel, use_panel_background=True):
        """Задает фон панели в соответствии с темой."""
        theme = theme_manager.get_theme()
        bg = theme['panel_bg'] if use_panel_background else theme['bg']
        panel.SetBackgroundColour(bg)
        panel.SetOwnBackgroundColour(bg)
        
    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        theme = theme_manager.get_theme()
        self.SetBackgroundColour(theme['bg'])
        self.SetOwnBackgroundColour(theme['bg'])
        
        quick_access_panel = wx.Panel(self)
        self._style_panel(quick_access_panel)
        quick_access_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        table_names = [
            ("👥 Актеры", "Актеры"),
            ("✍️ Авторы", "Авторы"),
            ("📜 Пьесы", "Пьесы"),
            ("🎬 Режиссеры", "Режиссеры"),
            ("🎭 Постановки", "Постановки"),
            ("📅 Спектакли", "Спектакли"),
            ("🔄 Репетиции", "Репетиции"),
            ("🎪 Роли", "Роли"),
            ("📍 Локации", "Локации"),
            ("🏛️ Театры", "Театры")
        ]
        
        self.quick_access_buttons = []  # Сохраняем ссылки на кнопки для масштабирования
        for emoji_name, table_name in table_names:
            btn = wx.Button(quick_access_panel, -1, emoji_name)
            self._style_primary_button(btn)
            # Улучшенная адаптивность кнопок - минимальный размер и отзывчивость
            btn.SetMinSize((80, 40))
            btn.Bind(wx.EVT_BUTTON, lambda e, tn=table_name: show_table(self.GetParent(), tn))

            self.quick_access_buttons.append(btn)
            quick_access_sizer.Add(btn, 1, wx.EXPAND | wx.RIGHT, 5)
        
        fullscreen_btn = wx.Button(quick_access_panel, -1, "⛶ Полный экран")
        self._style_primary_button(fullscreen_btn)
        fullscreen_btn.SetMinSize((135, 40))
        quick_access_sizer.Add(fullscreen_btn, 0, wx.LEFT, 10)
        
        def toggle_fullscreen(event):
            frame = self.GetTopLevelParent()
            if frame.IsFullScreen():
                frame.ShowFullScreen(False)
                fullscreen_btn.SetLabel("⛶ Полный экран")
            else:
                frame.ShowFullScreen(True)
                fullscreen_btn.SetLabel("⛶ Обычный режим")
        
        fullscreen_btn.Bind(wx.EVT_BUTTON, toggle_fullscreen)
        
        quick_access_panel.SetSizer(quick_access_sizer)
        main_sizer.Add(quick_access_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        title = wx.StaticText(self, -1, "🎭 Театральная система")
        title_font = wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        title.SetForegroundColour(theme['fg'])
        main_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER, 15)
        # Анимация появления заголовка
        
        if not db_initialized:
            loading_text = wx.StaticText(self, -1, "⏳ Загрузка данных...")
            loading_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            loading_text.SetForegroundColour(theme['fg'])
            main_sizer.Add(loading_text, 0, wx.ALL | wx.ALIGN_CENTER, 20)
            self.SetSizer(main_sizer)
            return
        
        # Это гарантирует актуальность данных после удаления в phpMyAdmin
        async def force_init_data():
            try:
                # Не логируем обновление при открытии дашборда (слишком часто)
                await refresh_all_data()
                await asyncio.sleep(0.2)  # Небольшая задержка для гарантии
                return True
            except Exception as e:
                logging.error(f"Ошибка принудительного обновления данных дашборда: {e}")
                return False
        
        future = run_async(force_init_data())
        if future:
            try:
                future.result(timeout=15)
                # После обновления данных обновляем интерфейс
                wx.CallLater(300, self.refresh_all_data)
            except Exception as e:
                logging.error(f"Ошибка обновления данных дашборда: {e}")
        
        filters_sizer = self.create_filters()
        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        metrics_sizer = self.create_metrics_cards()
        main_sizer.Add(metrics_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        charts_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        line_chart_sizer = self.create_line_chart()
        charts_sizer.Add(line_chart_sizer, 1, wx.EXPAND | wx.RIGHT, 5)
        
        pie_chart_sizer = self.create_pie_chart()
        charts_sizer.Add(pie_chart_sizer, 1, wx.EXPAND | wx.LEFT, 5)
        
        main_sizer.Add(charts_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        table_sizer = self.create_rehearsals_table()
        main_sizer.Add(table_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        control_panel = wx.Panel(self)
        self._style_panel(control_panel)
        control_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        refresh_btn = wx.Button(control_panel, -1, "🔄 Обновить данные")
        self._style_primary_button(refresh_btn)
        refresh_btn.SetMinSize((150, 40))
        export_btn = wx.Button(control_panel, -1, "📊 Экспорт отчета")
        self._style_primary_button(export_btn)
        export_btn.SetMinSize((150, 40))
        settings_btn = wx.Button(control_panel, -1, "⚙️ Настройки")
        self._style_primary_button(settings_btn)
        settings_btn.SetMinSize((120, 40))
        
        refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        export_btn.Bind(wx.EVT_BUTTON, self.on_export)
        settings_btn.Bind(wx.EVT_BUTTON, self.on_settings)
        
        control_sizer.Add(refresh_btn, 0, wx.RIGHT, 10)
        control_sizer.Add(export_btn, 0, wx.RIGHT, 10)
        control_sizer.Add(settings_btn, 0)
        
        control_panel.SetSizer(control_sizer)
        main_sizer.Add(control_panel, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        
        log_action("Дашборд открыт")
    
    def on_size(self, event):
        """Обработчик изменения размера окна для масштабирования иконок"""
        event.Skip()
        if not self.quick_access_buttons:
            return
        
        try:
            # Получаем текущий размер окна
            frame = self.GetTopLevelParent()
            if not frame:
                return
            
            width, height = frame.GetSize()
            # Базовый размер окна (1400x900)
            base_width = 1400
            base_height = 900
            
            # Вычисляем коэффициент масштабирования
            scale_x = width / base_width
            scale_y = height / base_height
            scale = min(scale_x, scale_y)  # Используем минимальный для сохранения пропорций
            
            # Ограничиваем масштаб от 0.5 до 1.5
            scale = max(0.5, min(1.5, scale))
            
            # Обновляем размер шрифта для всех кнопок
            font_size = int(self.base_font_size * scale)
            if font_size < 8:
                font_size = 8
            elif font_size > 16:
                font_size = 16
            
            font = wx.Font(font_size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            
            for btn in self.quick_access_buttons:
                if btn:
                    btn.SetFont(font)
                    btn.Refresh()
        except Exception as e:
            logging.error(f"Ошибка масштабирования иконок: {e}")
    
    def create_metrics_cards(self):
        """Создание карточек с метриками с сохранением ссылок для обновления"""
        theme = theme_manager.get_theme()
        metrics_box = wx.StaticBox(self, -1, "📊 Ключевые показатели")
        metrics_box.SetForegroundColour(theme['fg'])
        metrics_box.SetBackgroundColour(theme['panel_bg'])
        metrics_box.SetOwnBackgroundColour(theme['panel_bg'])
        metrics_sizer = wx.StaticBoxSizer(metrics_box, wx.HORIZONTAL)
        
        # Карточка репетиций
        rehearsals_card = wx.Panel(metrics_box)
        self._style_panel(rehearsals_card)
        rehearsals_sizer = wx.BoxSizer(wx.VERTICAL)
        rehearsals_title = wx.StaticText(rehearsals_card, -1, "🔄 Репетиций")
        rehearsals_title.SetForegroundColour(theme['fg'])
        self.metrics_cards['rehearsals'] = wx.StaticText(rehearsals_card, -1, str(metrics_data['total_rehearsals']))
        self.metrics_cards['rehearsals'].SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.metrics_cards['rehearsals'].SetForegroundColour(theme['fg'])
        
        rehearsals_sizer.Add(rehearsals_title, 0, wx.ALL, 5)
        rehearsals_sizer.Add(self.metrics_cards['rehearsals'], 0, wx.ALL, 5)
        rehearsals_card.SetSizer(rehearsals_sizer)
        
        # Карточка актеров
        actors_card = wx.Panel(metrics_box)
        self._style_panel(actors_card)
        actors_sizer = wx.BoxSizer(wx.VERTICAL)
        actors_title = wx.StaticText(actors_card, -1, "👥 Актеров")
        actors_title.SetForegroundColour(theme['fg'])
        self.metrics_cards['actors'] = wx.StaticText(actors_card, -1, str(metrics_data['actors_count']))
        self.metrics_cards['actors'].SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.metrics_cards['actors'].SetForegroundColour(theme['fg'])
        
        actors_sizer.Add(actors_title, 0, wx.ALL, 5)
        actors_sizer.Add(self.metrics_cards['actors'], 0, wx.ALL, 5)
        actors_card.SetSizer(actors_sizer)
        
        # Карточка постановок
        productions_card = wx.Panel(metrics_box)
        self._style_panel(productions_card)
        productions_sizer = wx.BoxSizer(wx.VERTICAL)
        productions_title = wx.StaticText(productions_card, -1, "🎭 Постановок")
        productions_title.SetForegroundColour(theme['fg'])
        self.metrics_cards['productions'] = wx.StaticText(productions_card, -1, str(metrics_data['productions_count']))
        self.metrics_cards['productions'].SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.metrics_cards['productions'].SetForegroundColour(theme['fg'])
        
        productions_sizer.Add(productions_title, 0, wx.ALL, 5)
        productions_sizer.Add(self.metrics_cards['productions'], 0, wx.ALL, 5)
        productions_card.SetSizer(productions_sizer)
        
        # Карточка ролей
        roles_card = wx.Panel(metrics_box)
        self._style_panel(roles_card)
        roles_sizer = wx.BoxSizer(wx.VERTICAL)
        roles_title = wx.StaticText(roles_card, -1, "🎪 Ролей")
        roles_title.SetForegroundColour(theme['fg'])
        self.metrics_cards['roles'] = wx.StaticText(roles_card, -1, str(metrics_data['roles_count']))
        self.metrics_cards['roles'].SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.metrics_cards['roles'].SetForegroundColour(theme['fg'])
        roles_sizer.Add(roles_title, 0, wx.ALL, 5)
        roles_sizer.Add(self.metrics_cards['roles'], 0, wx.ALL, 5)
        roles_card.SetSizer(roles_sizer)
        
        # Анимация появления карточек
        
        metrics_sizer.Add(rehearsals_card, 1, wx.EXPAND | wx.ALL, 5)
        metrics_sizer.Add(actors_card, 1, wx.EXPAND | wx.ALL, 5)
        metrics_sizer.Add(productions_card, 1, wx.EXPAND | wx.ALL, 5)
        metrics_sizer.Add(roles_card, 1, wx.EXPAND | wx.ALL, 5)
        
        return metrics_sizer
    
    def refresh_metrics(self):
        # Обновление значений в карточках метрик
        if hasattr(self, 'metrics_cards') and self.metrics_cards:
            try:
                # Проверяем, что объекты еще существуют
                if not hasattr(self, 'IsShown') or not self.IsShown():
                    return
                if 'rehearsals' in self.metrics_cards and self.metrics_cards['rehearsals']:
                    try:
                        self.metrics_cards['rehearsals'].SetLabel(str(metrics_data['total_rehearsals']))
                    except RuntimeError:
                        return
                if 'actors' in self.metrics_cards and self.metrics_cards['actors']:
                    try:
                        self.metrics_cards['actors'].SetLabel(str(metrics_data['actors_count']))
                    except RuntimeError:
                        return
                if 'productions' in self.metrics_cards and self.metrics_cards['productions']:
                    try:
                        self.metrics_cards['productions'].SetLabel(str(metrics_data['productions_count']))
                    except RuntimeError:
                        return
                if 'roles' in self.metrics_cards and self.metrics_cards['roles']:
                    try:
                        self.metrics_cards['roles'].SetLabel(str(metrics_data['roles_count']))
                    except RuntimeError:
                        return
                
                # Принудительное обновление отображения
                for card in self.metrics_cards.values():
                    if card:
                        try:
                            card.Refresh()
                            card.Update()
                        except RuntimeError:
                            pass
                # Не логируем обновление метрик (слишком часто)
            except Exception as e:
                logging.error(f"Ошибка обновления метрик: {e}")
    
    def create_filters(self):
        theme = theme_manager.get_theme()
        filters_box = wx.StaticBox(self, -1, "🔧 Фильтры")
        filters_box.SetForegroundColour(theme['fg'])
        filters_box.SetBackgroundColour(theme['panel_bg'])
        filters_box.SetOwnBackgroundColour(theme['panel_bg'])
        filters_sizer = wx.StaticBoxSizer(filters_box, wx.HORIZONTAL)
        
        period_label = wx.StaticText(filters_box, -1, "Период:")
        period_label.SetForegroundColour(theme['fg'])
        period_choice = wx.Choice(filters_box, -1, choices=['весь', 'неделя', 'месяц', 'квартал', 'год'])
        period_choice.SetSelection(0)
        period_choice.SetBackgroundColour(theme['text_ctrl_bg'])
        period_choice.SetForegroundColour(theme['text_ctrl_fg'])
        
        theatre_label = wx.StaticText(filters_box, -1, "Театр:")
        theatre_label.SetForegroundColour(theme['fg'])
        future = run_async(db_manager.get_unique_theatres())
        theatre_names = future.result(timeout=10) if future else []
        theatre_choices = ['все'] + sorted(theatre_names)
        theatre_choice = wx.Choice(filters_box, -1, choices=theatre_choices)
        theatre_choice.SetSelection(0)
        theatre_choice.SetBackgroundColour(theme['text_ctrl_bg'])
        theatre_choice.SetForegroundColour(theme['text_ctrl_fg'])
        
        director_label = wx.StaticText(filters_box, -1, "Режиссер:")
        director_label.SetForegroundColour(theme['fg'])
        future = run_async(db_manager.get_all_directors())
        directors = future.result(timeout=10) if future else []
        director_choices = ['все'] + [director['full_name'] for director in directors]
        director_choice = wx.Choice(filters_box, -1, choices=director_choices)
        director_choice.SetSelection(0)
        director_choice.SetBackgroundColour(theme['text_ctrl_bg'])
        director_choice.SetForegroundColour(theme['text_ctrl_fg'])
        
        apply_btn = wx.Button(filters_box, -1, "Применить")
        self._style_primary_button(apply_btn)
        apply_btn.SetMinSize((80, 30))
        
        def on_apply(event):
            filters['period'] = period_choice.GetStringSelection()
            filters['theatre'] = theatre_choice.GetStringSelection()
            filters['director'] = director_choice.GetStringSelection()
            # Не логируем применение фильтров (слишком часто)
            self.on_filter_change()
        
        apply_btn.Bind(wx.EVT_BUTTON, on_apply)
        
        filters_sizer.Add(period_label, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        filters_sizer.Add(period_choice, 0, wx.ALL, 5)
        filters_sizer.Add(theatre_label, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        filters_sizer.Add(theatre_choice, 0, wx.ALL, 5)
        filters_sizer.Add(director_label, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        filters_sizer.Add(director_choice, 0, wx.ALL, 5)
        filters_sizer.Add(apply_btn, 0, wx.ALL, 5)
        
        return filters_sizer
    
    def create_line_chart(self):
        chart_box = wx.StaticBox(self, -1, "📈 Динамика репетиций по месяцам")
        theme = theme_manager.get_theme()
        chart_box.SetForegroundColour(theme['fg'])
        chart_box.SetBackgroundColour(theme['panel_bg'])
        chart_sizer = wx.StaticBoxSizer(chart_box, wx.VERTICAL)
        
        bg_color = '#ffffff' if theme_manager.get_current_theme_name() == 'light' else '#1e1e1e'
        fig = Figure(facecolor=bg_color, figsize=(6, 4))
        ax = fig.add_subplot(111)
        
        self.update_line_chart(ax)
        
        fig.subplots_adjust(left=0.15, bottom=0.25, right=0.95, top=0.88, wspace=0.2, hspace=0.2)
        
        self.line_chart_canvas = FigureCanvas(chart_box, -1, fig)
        chart_sizer.Add(self.line_chart_canvas, 1, wx.ALL | wx.EXPAND, 5)
        
        return chart_sizer
    
    def update_line_chart(self, ax):
        ax.clear()
        theme = theme_manager.get_theme()
        is_dark = theme_manager.get_current_theme_name() == 'dark'
        
        bg_color = '#ffffff' if not is_dark else '#1e1e1e'
        fg_color = '#000000' if not is_dark else '#ffffff'
        grid_color = '#cccccc' if not is_dark else '#555555'
        legend_bg = '#ffffff' if not is_dark else '#323232'
        legend_edge = '#cccccc' if not is_dark else '#666666'
        
        months = []
        rehearsals_count = []
        
        if line_chart_data and len(line_chart_data) > 0:
            months = [item['month'] for item in line_chart_data]
            rehearsals_count = [item['count'] for item in line_chart_data]
            
            if len(months) == len(rehearsals_count) and len(rehearsals_count) > 0:
                x_positions = range(len(months))
                
                ax.bar(x_positions, rehearsals_count, color='#6496ff', alpha=0.8, label='Количество репетиций')
                ax.legend(loc='upper left', fontsize=9, facecolor=legend_bg, edgecolor=legend_edge, labelcolor=fg_color)
                
                ax.set_xticks(x_positions)
                ax.set_xticklabels(months, rotation=45, ha='right', fontsize=9, color=fg_color)
                
                max_count = max(rehearsals_count) if rehearsals_count else 1
                for i, v in enumerate(rehearsals_count):
                    if v > 0:
                        y_pos = v + max_count * 0.1
                        ax.text(i, y_pos, str(v), ha='center', va='bottom', fontsize=8, color=fg_color)
                
                max_val = max(rehearsals_count)
                ax.set_ylim(0, max_val * 1.2)
            else:
                ax.text(0.5, 0.5, 'Нет данных', horizontalalignment='center', 
                       verticalalignment='center', transform=ax.transAxes, fontsize=14, color=fg_color)
        else:
            ax.text(0.5, 0.5, 'Нет данных', horizontalalignment='center', 
                   verticalalignment='center', transform=ax.transAxes, fontsize=14, color=fg_color)
        
        ax.set_facecolor(bg_color)
        ax.grid(True, alpha=0.2, axis='y', color=grid_color)
        ax.set_xlabel('Месяцы', fontsize=10, color=fg_color)
        ax.set_ylabel('Количество репетиций', fontsize=10, color=fg_color)
        ax.tick_params(colors=fg_color)
        ax.set_title('Динамика репетиций по месяцам', fontsize=11, fontweight='bold', pad=25, color=fg_color)
    
    def create_pie_chart(self):
        pie_box = wx.StaticBox(self, -1, "🎭 Распределение пьес по жанрам")
        theme = theme_manager.get_theme()
        pie_box.SetForegroundColour(theme['fg'])
        pie_box.SetBackgroundColour(theme['panel_bg'])
        pie_sizer = wx.StaticBoxSizer(pie_box, wx.VERTICAL)
        
        bg_color = '#ffffff' if theme_manager.get_current_theme_name() == 'light' else '#1e1e1e'
        fig = Figure(facecolor=bg_color, figsize=(6, 4))
        ax = fig.add_subplot(111)
        
        self.update_pie_chart(ax)
        
        fig.tight_layout()
        
        self.pie_chart_canvas = FigureCanvas(pie_box, -1, fig)
        pie_sizer.Add(self.pie_chart_canvas, 1, wx.ALL | wx.EXPAND, 5)
        
        return pie_sizer
    
    def update_pie_chart(self, ax):
        ax.clear()
        theme = theme_manager.get_theme()
        is_dark = theme_manager.get_current_theme_name() == 'dark'
        
        bg_color = '#ffffff' if not is_dark else '#1e1e1e'
        fg_color = '#000000' if not is_dark else '#ffffff'
        legend_bg = '#ffffff' if not is_dark else '#323232'
        legend_edge = '#cccccc' if not is_dark else '#666666'
        
        if pie_chart_data and len(pie_chart_data) > 0:
            categories = [item['genre'] for item in pie_chart_data]
            category_values = [item['count'] for item in pie_chart_data]
            
            if len(categories) == len(category_values):
                colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFE66D', '#FF8E53', '#6A0572', '#1A535C', '#4ECDC4', '#FF6B6B']
                wedges, texts, autotexts = ax.pie(
                    category_values, 
                    labels=categories, 
                    autopct=lambda pct: f'{pct:.1f}%' if pct > 3 else '',
                    colors=colors[:len(categories)],
                    startangle=90,
                    textprops={'fontsize': 9, 'color': fg_color}
                )
                
                for text in texts:
                    text.set_color(fg_color)
                
                for autotext in autotexts:
                    autotext.set_color(fg_color)
                    autotext.set_fontweight('bold')
                
                legend = ax.legend(wedges, categories, title="Жанры", loc="center left", 
                         bbox_to_anchor=(1, 0, 0.5, 1), fontsize=9, 
                         facecolor=legend_bg, edgecolor=legend_edge, labelcolor=fg_color)
                if legend.get_title():
                    legend.get_title().set_color(fg_color)
            else:
                ax.text(0.5, 0.5, 'Нет данных', horizontalalignment='center', 
                       verticalalignment='center', transform=ax.transAxes, fontsize=14, color=fg_color)
        else:
            ax.text(0.5, 0.5, 'Нет данных', horizontalalignment='center', 
                   verticalalignment='center', transform=ax.transAxes, fontsize=14, color=fg_color)
        
        ax.set_facecolor(bg_color)
        ax.axis('equal')
        ax.set_title('Распределение пьес по жанрам', fontsize=12, fontweight='bold', color=fg_color)
    
    def create_rehearsals_table(self):
        table_box = wx.StaticBox(self, -1, "📅 Ближайшие репетиции")
        theme = theme_manager.get_theme()
        table_box.SetForegroundColour(theme['fg'])
        table_box.SetBackgroundColour(theme['panel_bg'])
        table_sizer = wx.StaticBoxSizer(table_box, wx.VERTICAL)
        
        headers = ["ID", "Дата и время", "Пьеса", "Режиссер", "Место", "Жанр", "Продолжительность", "Актеров"]
        
        self.rehearsals_grid = wx.grid.Grid(table_box)
        self.rehearsals_grid.CreateGrid(0, len(headers))
        self.rehearsals_grid.EnableEditing(False)
        self.rehearsals_grid.EnableGridLines(True)
        
        theme_manager.apply_theme(self.rehearsals_grid)
        
        for i, header in enumerate(headers):
            self.rehearsals_grid.SetColLabelValue(i, header)
        
        self.refresh_rehearsals_table()
        
        table_sizer.Add(self.rehearsals_grid, 1, wx.ALL | wx.EXPAND, 5)
        
        table_box.SetMinSize((-1, 200))
        
        return table_sizer
    
    def refresh_charts(self):
        try:
            if self.line_chart_canvas:
                fig = self.line_chart_canvas.figure
                bg_color = '#ffffff' if theme_manager.get_current_theme_name() == 'light' else '#1e1e1e'
                fig.set_facecolor(bg_color)
                ax = fig.axes[0] if fig.axes else None
                if ax:
                    self.update_line_chart(ax)
                    fig.subplots_adjust(left=0.15, bottom=0.25, right=0.95, top=0.85, wspace=0.2, hspace=0.2)
                    self.line_chart_canvas.draw()
                    self.line_chart_canvas.Refresh()
            
            if self.pie_chart_canvas:
                fig = self.pie_chart_canvas.figure
                bg_color = '#ffffff' if theme_manager.get_current_theme_name() == 'light' else '#1e1e1e'
                fig.set_facecolor(bg_color)
                if fig.axes:
                    self.update_pie_chart(fig.axes[0])
                    self.pie_chart_canvas.draw()
                    self.pie_chart_canvas.Refresh()
            
            if hasattr(self, 'rehearsals_grid') and self.rehearsals_grid:
                theme_manager.apply_theme(self.rehearsals_grid)
                self.rehearsals_grid.Refresh()
        except Exception as e:
            logging.error(f"Ошибка обновления графиков: {e}")
    
    def refresh_rehearsals_table(self):
        # Обновление таблицы репетиций с учетом фильтров - данные из БД
        if not hasattr(self, 'rehearsals_grid') or not self.rehearsals_grid:
            logging.warning("Таблица репетиций не найдена")
            return
        try:
            if not hasattr(self, 'IsShown') or not self.IsShown():
                return
        except RuntimeError:
            return
        
        try:
            # Удаляем старые строки
            if self.rehearsals_grid.GetNumberRows() > 0:
                self.rehearsals_grid.DeleteRows(0, self.rehearsals_grid.GetNumberRows())
            
            # Загружаем СВЕЖИЕ данные из БД с учетом фильтров
            # Не логируем загрузку данных репетиций (слишком часто)
            # Не логируем активные фильтры (слишком часто)
            
            # Данные уже загружены в rehearsals_data через refresh_all_data с учетом фильтров
            # rehearsals_data уже содержит отфильтрованные данные из БД
            filtered_rehearsals = rehearsals_data[:] if rehearsals_data else []
            
            # Не логируем количество полученных репетиций (слишком часто)
            
            # Добавляем отфильтрованные данные (даже если список пустой - показываем пустую таблицу)
            if len(filtered_rehearsals) > 0:
                self.rehearsals_grid.AppendRows(len(filtered_rehearsals))
                
                for i, row in enumerate(filtered_rehearsals):
                    for j, value in enumerate(row):
                        if j < self.rehearsals_grid.GetNumberCols():
                            self.rehearsals_grid.SetCellValue(i, j, str(value))
            else:
                # Не логируем пустую таблицу после фильтрации (слишком часто)
                pass
            
            self.rehearsals_grid.AutoSizeColumns()
            self.rehearsals_grid.ForceRefresh()
            self.Layout()
            self.Refresh()
            # Не логируем обновление таблицы репетиций (слишком часто)
        except Exception as e:
            logging.error(f"Ошибка обновления таблицы репетиций: {e}", exc_info=True)
    
    def refresh_all_data(self):
        # Полное обновление всех данных и интерфейса дашборда
        try:
            # Проверяем, что объект еще существует
            if not hasattr(self, 'IsShown') or not self.IsShown():
                return
            
            # Не логируем начало обновления интерфейса (слишком часто)
            
            # Обновляем метрики
            try:
                self.refresh_metrics()
                # Не логируем обновление метрик (слишком часто)
            except RuntimeError as e:
                logging.warning(f"Не удалось обновить метрики: {e}")
            
            # Обновляем графики
            try:
                self.refresh_charts()
                # Не логируем обновление графиков (слишком часто)
            except RuntimeError as e:
                logging.warning(f"Не удалось обновить графики: {e}")
            
            # Обновляем таблицу репетиций
            try:
                self.refresh_rehearsals_table()
                # Не логируем обновление таблицы репетиций (слишком часто)
            except RuntimeError as e:
                logging.warning(f"Не удалось обновить таблицу репетиций: {e}")
            
            # Принудительная перекомпоновка и обновление
            try:
                self.Layout()
                self.Refresh()
            except RuntimeError:
                return
            
            # Обновляем родительское окно
            try:
                frame = self.GetTopLevelParent()
                if frame:
                    frame.Layout()
                    frame.Refresh()
            except RuntimeError:
                pass
            
            # Не логируем успешное обновление интерфейса (слишком часто)
            
        except RuntimeError as e:
            logging.warning(f"Объект дашборда был удален: {e}")
        except Exception as e:
            logging.error(f"Ошибка полного обновления дашборда: {e}", exc_info=True)
    
    def on_refresh(self, event):
        """Обработчик нажатия кнопки обновления - ПРИНУДИТЕЛЬНОЕ обновление из БД"""
        log_action("Ручное обновление данных дашборда")
        
        # Показываем индикатор загрузки
        refresh_btn = event.GetEventObject()
        original_label = refresh_btn.GetLabel()
        refresh_btn.SetLabel("⏳ Обновление...")
        refresh_btn.Disable()
        
        async def force_refresh_all():
            """Принудительное обновление всех данных из БД без кеширования"""
            try:
                # Не логируем принудительное обновление всех данных (слишком часто)
                
                # Увеличиваем задержку для гарантии фиксации транзакций
                await asyncio.sleep(0.5)
                
                # ПРИНУДИТЕЛЬНО обновляем все данные из БД
                await refresh_all_data()
                
                # Дополнительная задержка
                await asyncio.sleep(0.3)
                
                # Запрашиваем СВЕЖИЕ данные напрямую из БД для дашборда
                await refresh_all_data()
                
                # Не логируем завершение принудительного обновления (слишком часто)
                return True
            except Exception as e:
                logging.error(f"Ошибка принудительного обновления: {e}", exc_info=True)
                return False
        
        def on_refresh_complete(success):
            # Восстанавливаем кнопку
            wx.CallAfter(refresh_btn.SetLabel, original_label)
            wx.CallAfter(refresh_btn.Enable)
            
            if success:
                # Принудительно обновляем интерфейс после загрузки данных из БД
                def update_ui():
                    try:
                        # Обновляем текущее представление (таблицу или дашборд)
                        refresh_current_view()
                        # Дополнительное обновление дашборда
                        frame = wx.GetApp().GetTopWindow() if wx.GetApp() else None
                        if frame:
                            children = frame.GetChildren()
                            if children:
                                current_panel = children[0]
                                if isinstance(current_panel, DashboardPanel):
                                    current_panel.refresh_all_data()
                        show_success("Данные успешно обновлены из базы")
                        log_action("Данные дашборда успешно обновлены")
                    except Exception as e:
                        logging.error(f"Ошибка обновления UI: {e}", exc_info=True)
                        show_error(f"Ошибка обновления интерфейса: {str(e)}")
                
                wx.CallAfter(update_ui)
            else:
                show_error("Ошибка при обновлении данных из базы")
                log_action("Ошибка обновления данных дашборда", logging.ERROR)
        
        # Запускаем принудительное обновление данных
        future = run_async(force_refresh_all())
        if future:
            future.add_done_callback(lambda f: on_refresh_complete(f.result() if not f.exception() else False))
        else:
            on_refresh_complete(False)
            show_error("Не удалось запустить обновление данных")
    
    def on_export(self, event):
        """Обработчик экспорта отчетов с выбором формата и пути."""
        try:
            from src.utils.export_manager import export_manager
            
            # Устанавливаем существующий db_manager
            if db_manager:
                export_manager.set_db_manager(db_manager)
            
            # Диалог выбора типа отчета
            dialog = wx.Dialog(self, title="Экспорт отчетов", size=(700, 550),
                              style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            panel = wx.Panel(dialog)
            sizer = wx.BoxSizer(wx.VERTICAL)
            
            title = wx.StaticText(panel, -1, "Выберите тип отчета для экспорта:")
            title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            sizer.Add(title, 0, wx.ALL, 15)
            
            # Радиокнопки для выбора типа отчета
            report_types = [
                ("📊 Статистический отчет", "statistical"),
                ("📋 Детальный отчет", "detailed"),
                ("📈 Полный Excel отчет", "excel"),
                ("📦 Все отчеты", "all")
            ]
            
            self.report_choice = wx.RadioBox(
                panel,
                choices=[rt[0] for rt in report_types],
                style=wx.RA_SPECIFY_COLS
            )
            self.report_choice.SetSelection(0)
            sizer.Add(self.report_choice, 0, wx.ALL | wx.EXPAND, 10)
            
            # Кнопки
            btn_sizer = wx.StdDialogButtonSizer()
            ok_btn = wx.Button(panel, wx.ID_OK, "Далее")
            ok_btn.SetDefault()
            cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
            btn_sizer.AddButton(ok_btn)
            btn_sizer.AddButton(cancel_btn)
            btn_sizer.Realize()
            sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
            
            panel.SetSizer(sizer)
            dialog.Center()
            
            if dialog.ShowModal() == wx.ID_OK:
                selected_idx = self.report_choice.GetSelection()
                report_type = report_types[selected_idx][1]
                dialog.Destroy()
                
                # Если выбраны все отчеты
                if report_type == 'all':
                    self._export_all_reports()
                    return
                
                # Показываем диалог выбора формата и пути
                report_names = {
                    'statistical': 'Статистический_отчет',
                    'detailed': 'Детальный_отчет',
                    'excel': 'Полный_отчет'
                }
                
                report_name = report_names.get(report_type, 'Отчет')
                formats = ['PDF', 'XLSX'] if report_type != 'excel' else ['XLSX']
                
                result = export_manager.show_export_dialog(
                    self, report_name, formats
                )
                
                if result and len(result) == 2:
                    format_type, filepath = result
                    if format_type and filepath:
                        # Запускаем экспорт асинхронно
                        self._run_export_async(report_type, format_type, filepath)
                    else:
                        show_error("Экспорт отменен")
                else:
                    show_error("Экспорт отменен")
            else:
                dialog.Destroy()
        except Exception as e:
            logging.error(f"Ошибка экспорта: {e}", exc_info=True)
            show_error(f"Ошибка экспорта: {e}")
    
    def _export_all_reports(self):
        """Экспорт всех отчетов по порядку"""
        try:
            from src.utils.export_manager import export_manager
            
            # Проверяем, что db_manager инициализирован
            if not db_manager:
                show_error("База данных не инициализирована")
                return
            
            # Устанавливаем существующий db_manager
            export_manager.set_db_manager(db_manager)
            
            # Показываем диалог выбора директории для сохранения всех отчетов
            with wx.DirDialog(
                self,
                "Выберите директорию для сохранения всех отчетов",
                defaultPath=os.path.join(os.getcwd(), 'reports'),
                style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
            ) as dir_dialog:
                if dir_dialog.ShowModal() == wx.ID_CANCEL:
                    return
                
                save_dir = dir_dialog.GetPath()
                
                # Экспортируем все отчеты по порядку
                reports_to_export = [
                    ('statistical', 'PDF', 'Статистический_отчет'),
                    ('detailed', 'PDF', 'Детальный_отчет'),
                    ('excel', 'XLSX', 'Полный_отчет')
                ]
                
                wx.CallAfter(show_success, f"Начало экспорта {len(reports_to_export)} отчетов...")
                
                async def export_all_task():
                    try:
                        # Убеждаемся, что db_manager установлен
                        if not export_manager.db_manager:
                            if db_manager:
                                export_manager.set_db_manager(db_manager)
                            else:
                                wx.CallAfter(show_error, "База данных не инициализирована")
                                return
                        
                        for i, (report_type, format_type, report_name) in enumerate(reports_to_export, 1):
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            format_ext = format_type.lower()
                            filepath = os.path.join(save_dir, f"{report_name}_{timestamp}.{format_ext}")
                            
                            wx.CallAfter(show_success, f"Экспорт {i}/{len(reports_to_export)}: {report_name}...")
                            
                            if report_type == 'statistical':
                                success = await export_manager.export_statistical_report(
                                    None, format_type, filepath
                                )
                            elif report_type == 'detailed':
                                success = await export_manager.export_detailed_report(
                                    None, format_type, filepath
                                )
                            elif report_type == 'excel':
                                success = await export_manager.export_excel_report(
                                    None, format_type, filepath
                                )
                            else:
                                success = False
                            
                            if success:
                                wx.CallAfter(log_action, f"Экспорт {report_name} завершен: {filepath}")
                            else:
                                wx.CallAfter(show_error, f"Ошибка при экспорте {report_name}")
                        
                        wx.CallAfter(show_success, f"Все отчеты успешно экспортированы в:\n{save_dir}")
                    except Exception as e:
                        logging.error(f"Ошибка экспорта всех отчетов: {e}", exc_info=True)
                        wx.CallAfter(show_error, f"Ошибка экспорта: {e}")
                
                future = run_async(export_all_task())
                if not future:
                    show_error("Не удалось запустить экспорт")
        except Exception as e:
            logging.error(f"Ошибка экспорта всех отчетов: {e}", exc_info=True)
            show_error(f"Ошибка экспорта всех отчетов: {e}")
    
    def _run_export_async(self, report_type: str, format_type: str, filepath: str):
        """Асинхронный запуск экспорта отчета"""
        from src.utils.export_manager import export_manager
        
        # Устанавливаем существующий db_manager перед запуском
        if not db_manager:
            wx.CallAfter(show_error, "База данных не инициализирована")
            return
        
        export_manager.set_db_manager(db_manager)
        
        async def export_task():
            try:
                # Убеждаемся, что db_manager установлен
                if not export_manager.db_manager:
                    if db_manager:
                        export_manager.set_db_manager(db_manager)
                    else:
                        wx.CallAfter(show_error, "База данных не инициализирована")
                        return
                
                # Экспортируем в зависимости от типа
                if report_type == 'statistical':
                    success = await export_manager.export_statistical_report(
                        None, format_type, filepath
                    )
                elif report_type == 'detailed':
                    success = await export_manager.export_detailed_report(
                        None, format_type, filepath
                    )
                elif report_type == 'excel':
                    success = await export_manager.export_excel_report(
                        None, format_type, filepath
                    )
                else:
                    wx.CallAfter(show_error, f"Неизвестный тип отчета: {report_type}")
                    return
                
                if success:
                    wx.CallAfter(show_success, f"Отчет успешно сохранен:\n{filepath}")
                    wx.CallAfter(log_action, f"Экспорт {report_type} отчета в {format_type}")
                else:
                    wx.CallAfter(show_error, "Ошибка при создании отчета")
            except Exception as e:
                logging.error(f"Ошибка экспорта: {e}", exc_info=True)
                wx.CallAfter(show_error, f"Ошибка экспорта: {e}")
        
        # Запускаем асинхронную задачу
        future = run_async(export_task())
        if future:
            # Показываем индикатор загрузки
            wx.CallAfter(show_success, "Экспорт запущен, пожалуйста подождите...")
    
    def on_settings(self, event):
        dialog = SettingsDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            wx.CallAfter(theme_manager.apply_theme_to_all_windows)
        dialog.Destroy()
    
    def on_filter_change(self):
        """Обработчик изменения фильтров"""
        log_action("Изменение фильтров дашборда")
        try:
            logging.info(f"Применение фильтров: период={filters.get('period')}, театр={filters.get('theatre')}, режиссер={filters.get('director')}")
            # Обновляем данные из БД с учетом фильтров
            def on_complete(success):
                if success:
                    wx.CallAfter(self.refresh_all_data)
                else:
                    logging.error("Ошибка обновления данных с фильтрами")
                    wx.CallAfter(self.refresh_all_data)
            
            future = run_async(refresh_all_data())
            if future:
                future.add_done_callback(lambda f: on_complete(f.result() if not f.exception() else False))
            else:
                on_complete(False)
        except Exception as e:
            logging.error(f"Ошибка применения фильтров: {e}", exc_info=True)
            wx.CallAfter(self.refresh_all_data)

def show_dashboard(parent):
    if parent:
        parent.DestroyChildren()
        dashboard_panel = DashboardPanel(parent)
        parent.GetSizer().Add(dashboard_panel, 1, wx.EXPAND)
        parent.Layout()
        parent.Refresh()
        
        async def force_refresh_on_open():
            try:
                # Не логируем обновление при открытии дашборда (слишком часто)
                await refresh_all_data()
                await asyncio.sleep(0.2)
                wx.CallAfter(dashboard_panel.refresh_all_data)
                return True
            except Exception as e:
                logging.error(f"Ошибка принудительного обновления при открытии дашборда: {e}")
                return False
        
        future = run_async(force_refresh_on_open())
        log_action("Дашборд открыт")

def show_table(parent, table_name):
    if parent:
        parent.DestroyChildren()
        table_panel = create_table_panel(parent, table_name)
        parent.GetSizer().Add(table_panel, 1, wx.EXPAND)
        parent.Layout()
        parent.Refresh()
        log_action(f"Открыта таблица: {table_name}")

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="🎭 Театральная система", size=(1920, 1080))
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(main_sizer)
        
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-1, 200])
        self.status_bar.SetStatusText("Готов к работе", 0)
        self.status_bar.SetStatusText("Дашборд", 1)
        
        show_dashboard(self)
        
        def apply_theme_delayed():
            theme_manager.apply_theme(self)
            if self.status_bar:
                theme_manager.apply_theme(self.status_bar)
            # Применяем тему ко всем дочерним элементам
            for child in self.GetChildren():
                theme_manager.apply_theme(child)
        
        wx.CallAfter(apply_theme_delayed)
        
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        logging.warning("Приложение запущено успешно")
    
    def on_close(self, event):
        try:
            if db_manager and event_loop:
                future = run_async(db_manager.close_pool())
                if future:
                    try:
                        future.result(timeout=5)
                    except Exception:
                        pass
            
            if event_loop and event_loop.is_running():
                event_loop.call_soon_threadsafe(event_loop.stop)
            
            self.Destroy()
        except Exception as e:
            logging.error(f"Ошибка при закрытии приложения: {e}")
            self.Destroy()

def main():
    global db_initialized
    
    # Запускаем цикл событий в отдельном потоке
    thread = threading.Thread(target=run_event_loop, daemon=True)
    thread.start()
    
    # Ждем инициализации базы данных
    import time
    max_wait = 30
    waited = 0
    while not db_initialized and waited < max_wait:
        time.sleep(1)
        waited += 1
    
    if not db_initialized:
        logging.error("Не удалось инициализировать базу данных")
    
    app = wx.App(False)
    
    try:
        app.SetAppName("Театральная система")
        app.SetVendorName("TheatreApp")
    except:
        pass
    
    frame = MainFrame()
    frame.Center()
    frame.Show()
    
    wx.CallAfter(lambda: theme_manager.apply_theme(frame))
    
    # Таймер для автоматического обновления данных каждые 100 секунд
    def auto_refresh(event):
        # Автоматическое обновление данных с сохранением фильтров и поиска
        try:
            update_dashboard_data()
            refresh_current_view()
        except Exception as e:
            logging.error(f"Ошибка автообновления: {e}")
    
    timer = wx.Timer(frame)
    frame.Bind(wx.EVT_TIMER, auto_refresh, timer)
    timer.Start(100000)
    
    app.MainLoop()

if __name__ == "__main__":
    main()


