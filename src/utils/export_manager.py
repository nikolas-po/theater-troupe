"""
Менеджер экспорта отчетов с поддержкой выбора формата и пути сохранения.
"""
import os
import asyncio
import logging
from typing import Optional, Tuple, List
from datetime import datetime

try:
    import wx
    WX_AVAILABLE = True
except ImportError:
    WX_AVAILABLE = False
    logging.warning("wxPython не доступен, диалоги выбора будут отключены")

from config.database import DB_CONFIG
from src.database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class ExportManager:
    """Менеджер для управления экспортом отчетов"""
    
    def __init__(self):
        self.db_manager = None
        self.reports_dir = os.path.join(os.getcwd(), 'reports')
        self._ensure_reports_dir()
    
    def set_db_manager(self, db_manager):
        """Устанавливает существующий менеджер базы данных"""
        self.db_manager = db_manager
        logger.info("Используется существующий менеджер базы данных")
    
    def _ensure_reports_dir(self):
        """Создает директорию для отчетов, если она не существует"""
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir, exist_ok=True)
            logger.info(f"Создана директория для отчетов: {self.reports_dir}")
    
    async def init_database(self):
        """Инициализация базы данных"""
        try:
            loop = asyncio.get_event_loop()
            self.db_manager = DatabaseManager(loop)
            success = await self.db_manager.init_pool()
            if success:
                logger.info("База данных успешно инициализирована для экспорта")
                return True
            logger.error("Не удалось инициализировать базу данных")
            return False
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            return False
    
    async def close_database(self):
        """Закрытие соединения с базой данных"""
        if self.db_manager:
            await self.db_manager.close_pool()
    
    def get_default_path(self, report_name: str, format_ext: str) -> str:
        """Получить путь по умолчанию для отчета"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_name}_{timestamp}.{format_ext}"
        return os.path.join(self.reports_dir, filename)
    
    def show_export_dialog(self, parent, report_name: str, 
                          formats: List[str] = None) -> Optional[Tuple[str, str]]:
        """
        Показывает диалог выбора формата и пути экспорта.
        
        Args:
            parent: Родительское окно wxPython (может быть None)
            report_name: Название отчета
            formats: Список доступных форматов (по умолчанию ['PDF', 'XLSX'])
        
        Returns:
            Tuple[format, path] или None если отменено или wxPython недоступен
        """
        if not WX_AVAILABLE:
            # Если wxPython недоступен, используем путь по умолчанию
            formats = formats or ['PDF', 'XLSX']
            format_ext = formats[0].lower()
            default_path = self.get_default_path(report_name, format_ext)
            logger.info(f"Используется путь по умолчанию: {default_path}")
            return formats[0], default_path
        
        try:
            from src.api.reports import show_export_dialog
            result = show_export_dialog(parent, report_name, formats or ['PDF', 'XLSX'])
            if result and len(result) == 2 and result[0] and result[1]:
                return result
        except Exception as e:
            logger.error(f"Ошибка показа диалога экспорта: {e}", exc_info=True)
            formats = formats or ['PDF', 'XLSX']
            format_ext = formats[0].lower()
            default_path = self.get_default_path(report_name, format_ext)
            return formats[0], default_path
        
        return None
    
    async def export_statistical_report(self, parent=None, 
                                       format_type: str = None, 
                                       filepath: str = None) -> bool:
        """
        Экспорт статистического отчета.
        
        Args:
            parent: Родительское окно для диалога
            format_type: Формат отчета ('PDF' или 'XLSX'), если None - показывается диалог
            filepath: Путь сохранения, если None - показывается диалог
        
        Returns:
            True если экспорт успешен, False в противном случае
        """
        if not format_type or not filepath:
            result = self.show_export_dialog(parent, "Статистический_отчет")
            if not result:
                return False
            format_type, filepath = result
        
        # Убеждаемся, что db_manager установлен перед экспортом
        if not self.db_manager:
            logger.error("DatabaseManager не установлен для экспорта статистического отчета")
            return False
        
        try:
            if format_type.upper() == 'PDF':
                from src.export_to_pdf import StatisticalReport
                logger.info(f"Создание статистического отчета с db_manager: {type(self.db_manager)}")
                report = StatisticalReport(self.db_manager)
                logger.info(f"Статистический отчет создан, db_manager установлен: {report.db_manager is not None}")
                return await report.generate_report(filepath)
            elif format_type.upper() == 'XLSX':
                # Для Excel статистический отчет можно добавить позже
                logger.warning("Статистический отчет в Excel пока не реализован")
                return False
            else:
                logger.error(f"Неподдерживаемый формат: {format_type}")
                return False
        except Exception as e:
            logger.error(f"Ошибка экспорта статистического отчета: {e}")
            return False
    
    async def export_detailed_report(self, parent=None,
                                    format_type: str = None,
                                    filepath: str = None) -> bool:
        """
        Экспорт детального отчета.
        
        Args:
            parent: Родительское окно для диалога
            format_type: Формат отчета ('PDF' или 'XLSX'), если None - показывается диалог
            filepath: Путь сохранения, если None - показывается диалог
        
        Returns:
            True если экспорт успешен, False в противном случае
        """
        if not format_type or not filepath:
            result = self.show_export_dialog(parent, "Детальный_отчет")
            if not result:
                return False
            format_type, filepath = result
        
        # Убеждаемся, что db_manager установлен перед экспортом
        if not self.db_manager:
            logger.error("DatabaseManager не установлен для экспорта детального отчета")
            return False
        
        try:
            if format_type.upper() == 'PDF':
                from src.export_to_pdf import DetailedReport
                logger.info(f"Создание детального отчета с db_manager: {type(self.db_manager)}")
                report = DetailedReport(self.db_manager)
                logger.info(f"Детальный отчет создан, db_manager установлен: {report.db_manager is not None}")
                return await report.generate_report(filepath)
            elif format_type.upper() == 'XLSX':
                # Для детального Excel отчета используем полный отчет
                return await self._export_xlsx_full(filepath)
            else:
                logger.error(f"Неподдерживаемый формат: {format_type}")
                return False
        except Exception as e:
            logger.error(f"Ошибка экспорта детального отчета: {e}")
            return False
    
    async def export_excel_report(self, parent=None,
                                 format_type: str = None,
                                 filepath: str = None) -> bool:
        """
        Экспорт Excel отчета (полный отчет с аналитикой).
        
        Args:
            parent: Родительское окно для диалога
            format_type: Формат отчета (должен быть 'XLSX')
            filepath: Путь сохранения, если None - показывается диалог
        
        Returns:
            True если экспорт успешен, False в противном случае
        """
        if not format_type or not filepath:
            result = self.show_export_dialog(parent, "Полный_отчет", ['XLSX'])
            if not result:
                return False
            format_type, filepath = result
        
        if format_type.upper() != 'XLSX':
            logger.error("Excel отчет поддерживает только формат XLSX")
            return False
        
        try:
            return await self._export_xlsx_full(filepath)
        except Exception as e:
            logger.error(f"Ошибка экспорта Excel отчета: {e}")
            return False
    
    async def _export_xlsx_detailed(self, filepath: str) -> bool:
        """Внутренний метод для экспорта детального Excel отчета"""
        # Здесь можно реализовать детальный Excel отчет
        # Пока используем полный отчет
        return await self._export_xlsx_full(filepath)
    
    async def _export_xlsx_full(self, filepath: str) -> bool:
        """Внутренний метод для экспорта полного Excel отчета"""
        try:
            from src.export_to_xlsx import create_report_with_path
            # Модифицируем функцию экспорта для работы с путем
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: create_report_with_path(filepath)
            )
            return result is not None
        except Exception as e:
            logger.error(f"Ошибка экспорта Excel отчета: {e}")
            return False


# Глобальный экземпляр менеджера экспорта
export_manager = ExportManager()

