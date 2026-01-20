"""
Модуль для генерации PDF отчетов из данных театральной системы.

Используемые библиотеки:
- os: работа с путями файловой системы (поиск шрифтов, определение директорий)
- asyncio: асинхронное выполнение запросов к базе данных
- logging: логирование процесса генерации отчетов (INFO, ERROR)
- datetime: форматирование дат и времени в отчетах
- reportlab: генерация PDF документов
  - reportlab.lib.pagesizes: размеры страниц (A4)
  - reportlab.pdfgen: низкоуровневая генерация PDF (не используется напрямую, оставлен для совместимости)
  - reportlab.platypus: высокоуровневая генерация PDF (SimpleDocTemplate, Table, Paragraph и т.д.)
  - reportlab.lib.styles: стили текста для PDF
  - reportlab.lib.colors: цветовая палитра для оформления
  - reportlab.lib.units: единицы измерения (inch)
  - reportlab.pdfbase: базовая функциональность PDF
  - reportlab.pdfbase.ttfonts: работа с TTF шрифтами для поддержки кириллицы
- matplotlib: создание графиков и диаграмм для вставки в PDF
  - matplotlib.use('Agg'): использование неинтерактивного бэкенда (без GUI)
  - matplotlib.pyplot: создание графиков (pie charts, bar charts)
- io: работа с байтовыми потоками для сохранения графиков в память перед вставкой в PDF
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Неинтерактивный бэкенд для генерации графиков без GUI
import io

# Универсальный импорт - работает и как модуль, и при прямом запуске
try:
    # Пытаемся импортировать как модуль (относительный импорт)
    from config.database import DB_CONFIG
    from src.database.connection import DatabaseManager
except ImportError:
    # Если не работает, пытаемся абсолютный импорт
    try:
        from config.database import DB_CONFIG
        from src.database.connection import DatabaseManager
    except ImportError:
        # Если и это не работает, добавляем родительскую директорию в путь
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config.database import DB_CONFIG
        from src.database.connection import DatabaseManager

db_manager = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PDFReporter:
    """Базовый класс для генерации PDF отчетов"""
    
    def __init__(self):
        self.cyrillic_font = self.setup_fonts()
        self.styles = getSampleStyleSheet()
        self.setup_styles()
    
    def setup_fonts(self):
        """Регистрация кириллических шрифтов"""
        try:
            font_paths = [
                'C:/Windows/Fonts/arial.ttf',
                'C:/Windows/Fonts/times.ttf',
                '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                '/Library/Fonts/Arial.ttf',
                '/System/Library/Fonts/Arial.ttf',
            ]
            
            cyrillic_font_path = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    cyrillic_font_path = font_path
                    break
            
            if cyrillic_font_path:
                pdfmetrics.registerFont(TTFont('CyrillicFont', cyrillic_font_path))
                pdfmetrics.registerFont(TTFont('CyrillicFont-Bold', cyrillic_font_path))
                logging.info(f"Используется кириллический шрифт: {cyrillic_font_path}")
                return 'CyrillicFont'
            else:
                logging.warning("Кириллические шрифты не найдены, используем Helvetica")
                return 'Helvetica'
                
        except Exception as e:
            logging.error(f"Ошибка настройки шрифтов: {e}")
            return 'Helvetica'
        
    def setup_styles(self):
        """Настройка стилей для PDF с кириллическими шрифтами"""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontName=f'{self.cyrillic_font}-Bold',
            fontSize=18,
            spaceAfter=30,
            alignment=1,
            textColor=colors.darkblue
        )
        
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontName=f'{self.cyrillic_font}-Bold',
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkblue
        )
        
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontName=self.cyrillic_font,
            fontSize=10,
            spaceAfter=6,
            leading=12,
            textColor=colors.black,
            alignment=0
        )
        
        self.table_header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontName=f'{self.cyrillic_font}-Bold',
            fontSize=9,
            spaceAfter=3,
            leading=11,
            alignment=1,  # Центрирование
            textColor=colors.white
        )
        
        self.table_cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['Normal'],
            fontName=self.cyrillic_font,
            fontSize=8,
            spaceAfter=3,
            leading=10,
            alignment=0,  # Выравнивание по левому краю
            wordWrap='CJK'  # Перенос слов
        )
        
        self.table_cell_center_style = ParagraphStyle(
            'TableCellCenter',
            parent=self.styles['Normal'],
            fontName=self.cyrillic_font,
            fontSize=8,
            spaceAfter=3,
            leading=10,
            alignment=1,  # Центрирование
            wordWrap='CJK'
        )
        
        self.table_cell_small_style = ParagraphStyle(
            'TableCellSmall',
            parent=self.styles['Normal'],
            fontName=self.cyrillic_font,
            fontSize=7,
            spaceAfter=2,
            leading=9,
            alignment=0,
            wordWrap='CJK'
        )

class StatisticalReport(PDFReporter):
    """Класс для генерации статистического отчета"""
    
    def __init__(self, db_manager_instance=None):
        super().__init__()
        self.metrics_data = {}
        self.chart_data = {}
        self.db_manager = db_manager_instance
        if not self.db_manager:
            logging.warning("StatisticalReport: db_manager_instance не передан, будет использован глобальный db_manager")
        else:
            logging.info(f"StatisticalReport: db_manager установлен: {type(self.db_manager)}")
        
    async def collect_data(self):
        """Сбор данных для статистического отчета с использованием агрегирующих SQL-запросов"""
        try:
            # Основные метрики через агрегирующие запросы
            total_actors = await self.get_total_count('actor')
            total_productions = await self.get_total_count('production')
            total_rehearsals = await self.get_total_count('rehearsal')
            total_roles = await self.get_total_count('role')
            total_plays = await self.get_total_count('play')
            total_performances = await self.get_total_count('performance')
            
            # Статистика по репетициям по месяцам
            monthly_rehearsals = await self.get_rehearsals_by_month()
            
            # Статистика по жанрам пьес
            plays_by_genre = await self.get_plays_by_genre()
            
            # Статистика по театрам
            productions_by_theatre = await self.get_productions_by_theatre()
            
            # Статистика по режиссерам
            productions_by_director = await self.get_productions_by_director()
            
            # Активность за последние 30 дней
            daily_activity = await self.get_daily_activity_last_30_days()
            
            # Топ-5 активных актеров
            top_actors = await self.get_top_actors_by_rehearsals(5)
            
            # Новые записи за последний месяц
            new_actors_month = await self.get_new_records_last_month('actor')
            new_productions_month = await self.get_new_records_last_month('production')
            
            self.metrics_data = {
                'total_actors': total_actors,
                'total_productions': total_productions,
                'total_rehearsals': total_rehearsals,
                'total_roles': total_roles,
                'total_plays': total_plays,
                'total_performances': total_performances,
                'monthly_rehearsals': monthly_rehearsals,
                'plays_by_genre': plays_by_genre,
                'productions_by_theatre': productions_by_theatre,
                'productions_by_director': productions_by_director,
                'daily_activity': daily_activity,
                'top_actors': top_actors,
                'new_actors_month': new_actors_month,
                'new_productions_month': new_productions_month
            }
            
            return True
        except Exception as e:
            logging.error(f"Ошибка сбора данных для статистического отчета: {e}")
            return False

    async def get_total_count(self, table_name):
        """Получить общее количество записей в таблице"""
        query = f"SELECT COUNT(*) as total FROM {table_name}"
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        result = await manager.execute_query(query)
        if result and len(result) > 0:
            return result[0].get('total', 0)
        return 0
    
    async def get_new_records_last_month(self, table_name):
        """Получить количество новых записей за последний месяц"""
        query = f"""
        SELECT COUNT(*) as count 
        FROM {table_name} 
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        result = await manager.execute_query(query)
        if result and len(result) > 0:
            return result[0].get('count', 0)
        return 0
    
    async def get_productions_by_theatre(self):
        """Статистика постановок по театрам"""
        query = """
        SELECT 
            t.id,
            t.name as theatre_name,
            COUNT(DISTINCT p.id) as production_count
        FROM production p
        JOIN performance perf ON p.id = perf.production_id
        JOIN location l ON perf.location_id = l.id
        JOIN theatre t ON l.theatre_id = t.id
        GROUP BY t.id, t.name
        ORDER BY production_count DESC
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)
    
    async def get_productions_by_director(self):
        """Статистика постановок по режиссерам"""
        query = """
        SELECT 
            d.id,
            d.full_name as director_name,
            COUNT(p.id) as production_count
        FROM production p
        JOIN director d ON p.director_id = d.id
        GROUP BY d.id, d.full_name
        ORDER BY production_count DESC
        LIMIT 10
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)
    
    async def get_daily_activity_last_30_days(self):
        """Активность по дням за последние 30 дней"""
        query = """
        SELECT 
            DATE(datetime) as activity_date,
            COUNT(*) as count
        FROM rehearsal 
        WHERE datetime >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DATE(datetime)
        ORDER BY activity_date DESC
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)
    
    async def get_rehearsals_by_month(self):
        """Статистика репетиций по месяцам"""
        query = """
        SELECT 
            DATE_FORMAT(datetime, '%%Y-%%m') as month,
            COUNT(*) as count
        FROM rehearsal 
        WHERE datetime >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(datetime, '%%Y-%%m')
        ORDER BY month DESC
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)
    
    async def get_plays_by_genre(self):
        """Распределение пьес по жанрам"""
        query = """
        SELECT 
            genre,
            COUNT(*) as count
        FROM play 
        GROUP BY genre
        ORDER BY count DESC
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)
    
    async def get_top_actors_by_rehearsals(self, limit=5):
        """Топ актеров по количеству репетиций"""
        query = """
        SELECT 
            a.id,
            a.full_name,
            COUNT(ar.rehearsal_id) as rehearsal_count
        FROM actor a
        LEFT JOIN actor_rehearsal ar ON a.id = ar.actor_id
        GROUP BY a.id, a.full_name
        ORDER BY rehearsal_count DESC
        LIMIT %s
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query, (limit,))
    
    def create_metrics_table(self):
        """Создание таблицы с метриками"""
        header_data = [
            Paragraph("Метрика", self.table_header_style),
            Paragraph("Значение", self.table_header_style)
        ]
        data = [header_data]
        
        # Добавляем данные с использованием Paragraph для правильного переноса
        data.append([
            Paragraph("Всего актеров", self.table_cell_style),
            Paragraph(str(self.metrics_data['total_actors']), self.table_cell_center_style)
        ])
        data.append([
            Paragraph("Всего постановок", self.table_cell_style),
            Paragraph(str(self.metrics_data['total_productions']), self.table_cell_center_style)
        ])
        data.append([
            Paragraph("Всего репетиций", self.table_cell_style),
            Paragraph(str(self.metrics_data['total_rehearsals']), self.table_cell_center_style)
        ])
        data.append([
            Paragraph("Всего ролей", self.table_cell_style),
            Paragraph(str(self.metrics_data['total_roles']), self.table_cell_center_style)
        ])
        data.append([
            Paragraph("Всего пьес", self.table_cell_style),
            Paragraph(str(self.metrics_data['total_plays']), self.table_cell_center_style)
        ])
        data.append([
            Paragraph("Всего спектаклей", self.table_cell_style),
            Paragraph(str(self.metrics_data['total_performances']), self.table_cell_center_style)
        ])
        data.append([
            Paragraph("Новых актеров за месяц", self.table_cell_style),
            Paragraph(str(self.metrics_data['new_actors_month']), self.table_cell_center_style)
        ])
        data.append([
            Paragraph("Новых постановок за месяц", self.table_cell_style),
            Paragraph(str(self.metrics_data['new_productions_month']), self.table_cell_center_style)
        ])
        
        table = Table(data, colWidths=[3.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90A4')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8F4F8')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        return table
    
    def create_genre_distribution_table(self):
        """Создание таблицы распределения по жанрам"""
        header_data = [
            Paragraph("Жанр", self.table_header_style),
            Paragraph("Количество пьес", self.table_header_style)
        ]
        data = [header_data]
        
        plays_by_genre = self.metrics_data.get('plays_by_genre', [])
        if not plays_by_genre or len(plays_by_genre) == 0:
            data.append([
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("0", self.table_cell_center_style)
            ])
        else:
            for item in plays_by_genre:
                genre = item.get('genre', 'Неизвестно')
                data.append([
                    Paragraph(genre, self.table_cell_style),
                    Paragraph(str(item.get('count', 0)), self.table_cell_center_style)
                ])
        
        table = Table(data, colWidths=[3.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6B8E7A')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F0F8F4')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        return table
    
    def create_monthly_stats_table(self):
        """Создание таблицы месячной статистики"""
        header_data = [
            Paragraph("Месяц", self.table_header_style),
            Paragraph("Количество репетиций", self.table_header_style)
        ]
        data = [header_data]
        
        monthly_rehearsals = self.metrics_data.get('monthly_rehearsals', [])
        if not monthly_rehearsals or len(monthly_rehearsals) == 0:
            data.append([
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("0", self.table_cell_center_style)
            ])
        else:
            for item in monthly_rehearsals:
                month = item.get('month', 'Неизвестно')
                data.append([
                    Paragraph(month, self.table_cell_style),
                    Paragraph(str(item.get('count', 0)), self.table_cell_center_style)
                ])
        
        table = Table(data, colWidths=[3.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#A67C7C')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F0F0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        return table
    
    def create_top_actors_table(self):
        """Создание таблицы топ-5 актеров"""
        header_data = [
            Paragraph("Актер", self.table_header_style),
            Paragraph("Количество репетиций", self.table_header_style)
        ]
        data = [header_data]
        
        top_actors = self.metrics_data.get('top_actors', [])
        if not top_actors or len(top_actors) == 0:
            data.append([
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("0", self.table_cell_center_style)
            ])
        else:
            for actor in top_actors:
                name = actor.get('full_name', 'Неизвестно')
                data.append([
                    Paragraph(name, self.table_cell_style),
                    Paragraph(str(actor.get('rehearsal_count', 0)), self.table_cell_center_style)
                ])
        
        table = Table(data, colWidths=[4*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#B8865B')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FFF8F0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        return table
    
    def create_theatre_stats_table(self):
        """Создание таблицы статистики по театрам"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("Название театра", self.table_header_style),
            Paragraph("Количество постановок", self.table_header_style)
        ]
        data = [header_data]
        
        productions_by_theatre = self.metrics_data.get('productions_by_theatre', [])
        if not productions_by_theatre or len(productions_by_theatre) == 0:
            data.append([
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("0", self.table_cell_center_style)
            ])
        else:
            for idx, item in enumerate(productions_by_theatre, start=1):
                theatre_name = item.get('theatre_name', 'Неизвестно')
                data.append([
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(theatre_name, self.table_cell_style),
                    Paragraph(str(item.get('production_count', 0)), self.table_cell_center_style)
                ])
        
        table = Table(data, colWidths=[0.8*inch, 3.2*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6B8E7A')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F0F8F4')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        return table
    
    def create_director_stats_table(self):
        """Создание таблицы статистики по режиссерам"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("ФИО режиссера", self.table_header_style),
            Paragraph("Количество постановок", self.table_header_style)
        ]
        data = [header_data]
        
        productions_by_director = self.metrics_data.get('productions_by_director', [])
        if not productions_by_director or len(productions_by_director) == 0:
            data.append([
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("0", self.table_cell_center_style)
            ])
        else:
            for idx, item in enumerate(productions_by_director, start=1):
                director_name = item.get('director_name', 'Неизвестно')
                data.append([
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(director_name, self.table_cell_style),
                    Paragraph(str(item.get('production_count', 0)), self.table_cell_center_style)
                ])
        
        table = Table(data, colWidths=[0.8*inch, 3.2*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9370DB')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F0FF')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        return table
    
    def generate_chart_image(self, chart_type='genre'):
        """Генерация изображения диаграммы"""
        try:
            plt.figure(figsize=(8, 6))
            
            if chart_type == 'genre' and self.metrics_data.get('plays_by_genre'):
                genres = [item.get('genre', 'Неизвестно') for item in self.metrics_data['plays_by_genre']]
                counts = [item.get('count', 0) for item in self.metrics_data['plays_by_genre']]
                
                plt.pie(counts, labels=genres, autopct='%1.1f%%', startangle=90)
                plt.title('Распределение пьес по жанрам')
                
            elif chart_type == 'monthly' and self.metrics_data.get('monthly_rehearsals'):
                months = [item.get('month', '') for item in self.metrics_data['monthly_rehearsals']]
                counts = [item.get('count', 0) for item in self.metrics_data['monthly_rehearsals']]
                
                plt.bar(months, counts, color='skyblue')
                plt.title('Репетиции по месяцам')
                plt.xticks(rotation=45)
                plt.ylabel('Количество репетиций')
            
            plt.tight_layout()
            
            # Сохраняем изображение в буфер
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close()
            
            return img_buffer
            
        except Exception as e:
            logging.error(f"Ошибка генерации диаграммы: {e}")
            return None
    
    async def generate_report(self, filename=None):
        """Генерация полного отчета"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Статистический_отчет_{timestamp}.pdf"
        
        try:
            # Собираем данные
            success = await self.collect_data()
            if not success:
                logging.error("Не удалось собрать данные для отчета")
                return False
            
            # Создаем документ
            doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=1*inch)
            story = []
            
            # Титульная страница
            title = Paragraph("СТАТИСТИЧЕСКИЙ ОТЧЕТ", self.title_style)
            story.append(title)
            
            subtitle = Paragraph("Театральная система управления", self.heading_style)
            story.append(subtitle)
            
            date_info = Paragraph(f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M')}", self.normal_style)
            story.append(date_info)
            
            story.append(Spacer(1, 0.5*inch))
            
            author = Paragraph("Сгенерировано автоматической системой отчетности", self.normal_style)
            story.append(author)
            
            story.append(PageBreak())
            
            # Раздел 1: Общая статистика
            section1_title = Paragraph("1. ОБЩАЯ СТАТИСТИКА СИСТЕМЫ", self.heading_style)
            story.append(section1_title)
            story.append(Spacer(1, 0.1*inch))
            
            metrics_table = self.create_metrics_table()
            story.append(metrics_table)
            
            story.append(PageBreak())
            
            # Раздел 2: Распределение по жанрам
            section2_title = Paragraph("2. РАСПРЕДЕЛЕНИЕ ПЬЕС ПО ЖАНРАМ", self.heading_style)
            story.append(section2_title)
            story.append(Spacer(1, 0.1*inch))
            
            genre_table = self.create_genre_distribution_table()
            story.append(genre_table)
            
            # Добавляем круговую диаграмму
            genre_chart = self.generate_chart_image('genre')
            if genre_chart:
                story.append(Spacer(1, 0.2*inch))
                chart_title = Paragraph("Диаграмма распределения по жанрам:", self.normal_style)
                story.append(chart_title)
                chart_img = Image(genre_chart, width=5*inch, height=3*inch)
                story.append(chart_img)
            
            story.append(PageBreak())
            
            # Раздел 3: Статистика репетиций
            section3_title = Paragraph("3. СТАТИСТИКА РЕПЕТИЦИЙ", self.heading_style)
            story.append(section3_title)
            story.append(Spacer(1, 0.1*inch))
            
            monthly_table = self.create_monthly_stats_table()
            story.append(monthly_table)
            
            # Добавляем столбчатую диаграмму
            monthly_chart = self.generate_chart_image('monthly')
            if monthly_chart:
                story.append(Spacer(1, 0.2*inch))
                chart_title = Paragraph("Диаграмма репетиций по месяцам:", self.normal_style)
                story.append(chart_title)
                chart_img = Image(monthly_chart, width=5*inch, height=3*inch)
                story.append(chart_img)
            
            story.append(PageBreak())
            
            # Раздел 4: Топ-5 актеров
            section4_title = Paragraph("4. ТОП-5 АКТЕРОВ ПО АКТИВНОСТИ", self.heading_style)
            story.append(section4_title)
            story.append(Spacer(1, 0.1*inch))
            
            top_actors_table = self.create_top_actors_table()
            story.append(top_actors_table)
            
            story.append(PageBreak())
            
            # Раздел 5: Статистика по театрам
            section5_title = Paragraph("5. СТАТИСТИКА ПОСТАНОВОК ПО ТЕАТРАМ", self.heading_style)
            story.append(section5_title)
            story.append(Spacer(1, 0.1*inch))
            
            theatre_table = self.create_theatre_stats_table()
            story.append(theatre_table)
            
            story.append(PageBreak())
            
            # Раздел 6: Статистика по режиссерам
            section6_title = Paragraph("6. СТАТИСТИКА ПОСТАНОВОК ПО РЕЖИССЕРАМ", self.heading_style)
            story.append(section6_title)
            story.append(Spacer(1, 0.1*inch))
            
            director_stats_table = self.create_director_stats_table()
            story.append(director_stats_table)
            
            story.append(PageBreak())
            
            # Раздел 7: Анализ данных
            section7_title = Paragraph("7. АНАЛИЗ ДАННЫХ И ВЫВОДЫ", self.heading_style)
            story.append(section7_title)
            story.append(Spacer(1, 0.1*inch))
            
            analysis_text = f"""
            <b>Ключевые выводы:</b>
            <br/><br/>
            • Общее количество активных сущностей в системе: {self.metrics_data['total_actors']} актеров, {self.metrics_data['total_productions']} постановок, {self.metrics_data['total_rehearsals']} репетиций
            <br/>
            • Распределение по жанрам отражает творческое направление театра
            <br/>
            • Динамика репетиций указывает на активность подготовки постановок
            <br/>
            • За последний месяц добавлено: {self.metrics_data['new_actors_month']} новых актеров, {self.metrics_data['new_productions_month']} новых постановок
            <br/>
            • Статистика используется для оптимизации планирования и распределения ресурсов
            <br/>
            • Топ-5 актеров показывает наиболее активных участников театрального процесса
            """
            
            analysis_para = Paragraph(analysis_text, self.normal_style)
            story.append(analysis_para)
            
            # Строим документ
            doc.build(story)
            logging.info(f"Статистический отчет успешно создан: {filename}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка генерации статистического отчета: {e}")
            return False

class DetailedReport(PDFReporter):
    """Класс для генерации детального табличного отчета"""
    
    def __init__(self, db_manager_instance=None):
        super().__init__()
        self.tables_data = {}
        # Отдельные атрибуты для каждого типа данных
        self.actors_data = []
        self.productions_data = []
        self.rehearsals_data = []
        self.plays_data = []
        self.authors_data = []
        self.directors_data = []
        self.performances_data = []
        self.db_manager = db_manager_instance
        if not self.db_manager:
            logging.warning("DetailedReport: db_manager_instance не передан, будет использован глобальный db_manager")
        else:
            logging.info(f"DetailedReport: db_manager установлен: {type(self.db_manager)}")
        
    async def collect_data(self, start_date=None, end_date=None):
        """Сбор данных для детального отчета"""
        try:
            logging.info("Начало сбора данных для детального отчета")
            
            # Получаем данные из всех таблиц БД
            actors = await self.get_actors_grouped_by_id()
            productions = await self.get_all_productions_with_details()
            rehearsals = await self.get_all_rehearsals_with_details()
            plays = await self.get_all_plays()
            authors = await self.get_all_authors()
            directors = await self.get_all_directors()
            performances = await self.get_all_performances_with_details()
            
            # Сохраняем данные в отдельных переменных
            self.actors_data = actors if actors else []
            self.productions_data = productions if productions else []
            self.rehearsals_data = rehearsals if rehearsals else []
            self.plays_data = plays if plays else []
            self.authors_data = authors if authors else []
            self.directors_data = directors if directors else []
            self.performances_data = performances if performances else []
            
            # Также сохраняем в общем словаре для обратной совместимости
            self.tables_data = {
                'actors': self.actors_data,
                'productions': self.productions_data,
                'rehearsals': self.rehearsals_data,
                'plays': self.plays_data,
                'authors': self.authors_data,
                'directors': self.directors_data,
                'performances': self.performances_data
            }
            
            # Детальное логирование
            logging.info(f"Актеров: {len(self.actors_data)}")
            logging.info(f"Постановок: {len(self.productions_data)}")
            logging.info(f"Репетиций: {len(self.rehearsals_data)}")
            logging.info(f"Пьес: {len(self.plays_data)}")
            logging.info(f"Авторов: {len(self.authors_data)}")
            logging.info(f"Режиссеров: {len(self.directors_data)}")
            logging.info(f"Спектаклей: {len(self.performances_data)}")
            
            return True
        except Exception as e:
            logging.error(f"Ошибка сбора данных для детального отчета: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    async def generate_report(self, filename=None):
        """Генерация детального отчета"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Детальный_отчет_{timestamp}.pdf"
        
        # Убеждаемся, что путь существует
        import os
        directory = os.path.dirname(filename) if os.path.dirname(filename) else os.getcwd()
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        try:
            # Собираем данные
            success = await self.collect_data()
            if not success:
                logging.error("Не удалось собрать данные для детального отчета")
                return False
            
            # Создаем документ
            doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=1*inch)
            story = []
            
            # Титульная страница
            title = Paragraph("ДЕТАЛЬНЫЙ ОТЧЕТ ПО ДАННЫМ СИСТЕМЫ", self.title_style)
            story.append(title)
            
            subtitle = Paragraph("Театральная система управления", self.heading_style)
            story.append(subtitle)
            
            date_info = Paragraph(f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M')}", self.normal_style)
            story.append(date_info)
            
            story.append(Spacer(1, 0.5*inch))
            
            total_records = sum(len(data) for data in self.tables_data.values())
            records_info = Paragraph(f"Всего записей в отчете: {total_records}", self.normal_style)
            story.append(records_info)
            
            story.append(PageBreak())
            
            # Оглавление
            toc_title = Paragraph("ОГЛАВЛЕНИЕ", self.heading_style)
            story.append(toc_title)
            story.append(Spacer(1, 0.3*inch))
            
            # Определяем доступные разделы
            sections = []
            if len(self.actors_data) > 0:
                sections.append(('actors', 'Актеры', 'Информация об актерах театральной труппы'))
            if len(self.productions_data) > 0:
                sections.append(('productions', 'Постановки', 'Список постановок с деталями'))
            if len(self.rehearsals_data) > 0:
                sections.append(('rehearsals', 'Репетиции', 'Расписание и информация о репетициях'))
            if len(self.performances_data) > 0:
                sections.append(('performances', 'Спектакли', 'Расписание спектаклей'))
            if len(self.plays_data) > 0:
                sections.append(('plays', 'Пьесы', 'Каталог пьес'))
            if len(self.authors_data) > 0:
                sections.append(('authors', 'Авторы', 'Информация об авторах пьес'))
            if len(self.directors_data) > 0:
                sections.append(('directors', 'Режиссеры', 'Информация о режиссерах'))
            
            # Добавляем разделы в оглавление
            if len(sections) == 0:
                no_data = Paragraph("В системе отсутствуют данные для отображения", self.normal_style)
                story.append(no_data)
            else:
                for i, (key, name, desc) in enumerate(sections):
                    toc_item = Paragraph(f"<b>{i+1}. {name}</b><br/>{desc}", self.normal_style)
                    story.append(toc_item)
                    story.append(Spacer(1, 0.15*inch))
            
            story.append(PageBreak())
            
            # Добавляем каждый раздел с данными
            for i, (key, name, desc) in enumerate(sections):
                section_title = Paragraph(f"{i+1}. {name.upper()}", self.heading_style)
                story.append(section_title)
                story.append(Spacer(1, 0.1*inch))
                
                # Используем прямые переменные вместо словаря tables_data
                if key == 'actors':
                    data_list = self.actors_data
                    count = len(self.actors_data)
                    table = self.create_actors_table()
                elif key == 'productions':
                    data_list = self.productions_data
                    count = len(self.productions_data)
                    table = self.create_productions_table()
                elif key == 'rehearsals':
                    data_list = self.rehearsals_data
                    count = len(self.rehearsals_data)
                    table = self.create_rehearsals_table()
                elif key == 'performances':
                    data_list = self.performances_data
                    count = len(self.performances_data)
                    table = self.create_performances_table()
                elif key == 'plays':
                    data_list = self.plays_data
                    count = len(self.plays_data)
                    table = self.create_plays_table()
                elif key == 'authors':
                    data_list = self.authors_data
                    count = len(self.authors_data)
                    table = self.create_authors_table()
                elif key == 'directors':
                    data_list = self.directors_data
                    count = len(self.directors_data)
                    table = self.create_directors_table()
                else:
                    continue
                
                count_info = Paragraph(f"Всего записей: {count}", self.normal_style)
                story.append(count_info)
                story.append(Spacer(1, 0.1*inch))
                
                story.append(table)
                
                # Добавляем разрыв страницы только если это не последний раздел
                if i < len(sections) - 1:
                    story.append(PageBreak())
            
            # Заключительная страница (только если есть разделы)
            if len(sections) > 0:
                story.append(PageBreak())
                conclusion_title = Paragraph("ИНФОРМАЦИЯ ОБ ОТЧЕТЕ", self.heading_style)
                story.append(conclusion_title)
                
                conclusion_text = f"""
                <b>Сводная информация:</b>
                <br/><br/>
                • Отчет содержит данные из {len(sections)} различных разделов системы
                <br/>
                • Всего обработано записей: {total_records}
                <br/>
                • Данные актуальны на: {datetime.now().strftime('%d.%m.%Y %H:%M')}
                <br/>
                • Отчет сгенерирован автоматической системой
                <br/>
                • Для получения дополнительной информации обратитесь к администратору системы
                """
                
                conclusion_para = Paragraph(conclusion_text, self.normal_style)
                story.append(conclusion_para)
            
            # Строим документ
            doc.build(story)
            logging.info(f"Детальный отчет успешно создан: {filename}")
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка генерации детального отчета: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    # Методы для получения данных из БД
    async def get_actors_grouped_by_id(self):
        """Получить всех актеров с группировкой по ID и статистикой"""
        query = """
        SELECT 
            a.id,
            a.full_name,
            a.experience,
            COUNT(DISTINCT ar.rehearsal_id) as rehearsal_count,
            COUNT(DISTINCT ap.production_id) as production_count
        FROM actor a
        LEFT JOIN actor_rehearsal ar ON a.id = ar.actor_id
        LEFT JOIN actor_production ap ON a.id = ap.actor_id
        GROUP BY a.id, a.full_name, a.experience
        ORDER BY a.id
        """
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)

    async def get_all_productions_with_details(self, start_date=None, end_date=None):
        """Получить все постановки с деталями"""
        query = """
        SELECT p.id, p.title, p.production_date, 
            pl.id as play_id, pl.title as play_title, pl.genre,
            d.id as director_id, d.full_name as director_name
        FROM production p
        JOIN play pl ON p.play_id = pl.id
        JOIN director d ON p.director_id = d.id
        ORDER BY p.production_date DESC
        """
        
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)

    async def get_all_rehearsals_with_details(self, start_date=None, end_date=None):
        """Получить все репетиции с деталями"""
        query = """
        SELECT r.id, r.datetime,
            t.id as theatre_id, t.name as theatre_name, 
            l.id as location_id, l.hall_name,
            pr.id as production_id, pr.title as production_title
        FROM rehearsal r
        JOIN location l ON r.location_id = l.id
        JOIN theatre t ON l.theatre_id = t.id
        JOIN production pr ON r.production_id = pr.id
        ORDER BY r.datetime DESC
        """
        
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)

    async def get_all_plays(self):
        """Получить все пьесы"""
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query("SELECT * FROM play ORDER BY id")

    async def get_all_authors(self):
        """Получить всех авторов"""
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query("SELECT * FROM author ORDER BY id")

    async def get_all_directors(self):
        """Получить всех режиссеров"""
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query("SELECT * FROM director ORDER BY id")

    async def get_all_performances_with_details(self, start_date=None, end_date=None):
        """Получить все спектакли с деталями"""
        query = """
        SELECT p.id, p.datetime,
            t.id as theatre_id, t.name as theatre_name, 
            l.id as location_id, l.hall_name,
            pr.id as production_id, pr.title as production_title
        FROM performance p
        JOIN location l ON p.location_id = l.id
        JOIN theatre t ON l.theatre_id = t.id
        JOIN production pr ON p.production_id = pr.id
        ORDER BY p.datetime DESC
        """
        
        manager = self.db_manager if self.db_manager else db_manager
        if not manager:
            raise RuntimeError("DatabaseManager не инициализирован")
        return await manager.execute_query(query)

    # Вспомогательные методы
    def truncate_text(self, text, max_length=200):
        """Обрезка текста с добавлением многоточия"""
        if not text:
            return ""
        if len(text) > max_length:
            return text[:max_length-3] + "..."
        return text

    def format_date_for_display(self, date_value):
        """Форматирование даты для отображения"""
        if not date_value:
            return ''
        try:
            if hasattr(date_value, 'strftime'):
                return date_value.strftime('%d.%m.%Y')
            elif isinstance(date_value, str):
                if len(date_value) >= 10:
                    return date_value[:10]
                return date_value
            return str(date_value)
        except:
            return str(date_value)

    def format_datetime_for_display(self, datetime_value):
        """Форматирование даты и времени для отображения"""
        if not datetime_value:
            return ''
        try:
            if hasattr(datetime_value, 'strftime'):
                return datetime_value.strftime('%d.%m.%Y %H:%M')
            elif isinstance(datetime_value, str):
                if ' ' in datetime_value:
                    parts = datetime_value.split(' ')
                    if len(parts) >= 2:
                        date_part = parts[0]
                        time_part = parts[1][:5]
                        return f"{date_part} {time_part}"
                elif len(datetime_value) >= 16:
                    return datetime_value[:16]
                return datetime_value
            return str(datetime_value)
        except:
            return str(datetime_value)

    # Методы создания таблиц с использованием Paragraph для всех ячеек
    def create_actors_table(self):
        """Создание таблицы актеров"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("ФИО", self.table_header_style),
            Paragraph("Опыт", self.table_header_style),
            Paragraph(" Кол-во Репетиций", self.table_header_style),
            Paragraph("Кол- во Постановок", self.table_header_style)
        ]
        data = [header_data]
        
        actors = self.actors_data
        if not actors:
            no_data_row = [
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_center_style)
            ]
            data.append(no_data_row)
        else:
            for idx, actor in enumerate(actors, start=1):
                full_name = actor.get('full_name', 'Не указано') or 'Не указано'
                experience = actor.get('experience', 'Не указано') or 'Не указано'
                
                row = [
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(full_name, self.table_cell_style),
                    Paragraph(experience, self.table_cell_style),
                    Paragraph(str(actor.get('rehearsal_count', 0)), self.table_cell_center_style),
                    Paragraph(str(actor.get('production_count', 0)), self.table_cell_center_style)
                ]
                data.append(row)
        
        # Оптимальные ширины столбцов для A4
        col_widths = [0.5*inch, 2.0*inch, 2.0*inch, 0.8*inch, 0.8*inch]
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90A4')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 0), (4, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8F4F8')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        return table

    def create_productions_table(self):
        """Создание таблицы постановок"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("Название", self.table_header_style),
            Paragraph("Дата", self.table_header_style),
            Paragraph("Пьеса", self.table_header_style),
            Paragraph("Режиссер", self.table_header_style)
        ]
        data = [header_data]
        
        productions = self.productions_data
        if not productions:
            no_data_row = [
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style)
            ]
            data.append(no_data_row)
        else:
            for idx, production in enumerate(productions, start=1):
                title = production.get('title', 'Не указано') or 'Не указано'
                play_title = production.get('play_title', 'Не указано') or 'Не указано'
                director_name = production.get('director_name', 'Не указано') or 'Не указано'
                
                row = [
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(title, self.table_cell_style),
                    Paragraph(self.format_date_for_display(production.get('production_date')) or 'Не указано', self.table_cell_center_style),
                    Paragraph(play_title, self.table_cell_style),
                    Paragraph(director_name, self.table_cell_style)
                ]
                data.append(row)
        
        col_widths = [0.5*inch, 2.0*inch, 0.8*inch, 1.5*inch, 1.7*inch]
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6B8E7A')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F0F8F4')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        return table

    def create_rehearsals_table(self):
        """Создание таблицы репетиций"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("Дата и время", self.table_header_style),
            Paragraph("Место", self.table_header_style),
            Paragraph("Постановка", self.table_header_style)
        ]
        data = [header_data]
        
        rehearsals = self.rehearsals_data
        if not rehearsals:
            no_data_row = [
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style)
            ]
            data.append(no_data_row)
        else:
            for idx, rehearsal in enumerate(rehearsals, start=1):
                theatre_name = rehearsal.get('theatre_name', 'Не указано') or 'Не указано'
                hall_name = rehearsal.get('hall_name', 'Не указано') or 'Не указано'
                location = f"{theatre_name}, {hall_name}" if theatre_name != 'Не указано' or hall_name != 'Не указано' else 'Не указано'
                production_title = rehearsal.get('production_title', 'Не указано') or 'Не указано'
                
                row = [
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(self.format_datetime_for_display(rehearsal.get('datetime')) or 'Не указано', self.table_cell_center_style),
                    Paragraph(location, self.table_cell_style),
                    Paragraph(production_title, self.table_cell_style)
                ]
                data.append(row)
        
        col_widths = [0.5*inch, 1.2*inch, 2.0*inch, 2.8*inch]
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#A67C7C')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F0F0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        return table

    def create_performances_table(self):
        """Создание таблицы спектаклей"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("Дата и время", self.table_header_style),
            Paragraph("Место", self.table_header_style),
            Paragraph("Постановка", self.table_header_style)
        ]
        data = [header_data]
        
        performances = self.performances_data
        if not performances:
            no_data_row = [
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style)
            ]
            data.append(no_data_row)
        else:
            for idx, performance in enumerate(performances, start=1):
                theatre_name = performance.get('theatre_name', 'Не указано') or 'Не указано'
                hall_name = performance.get('hall_name', 'Не указано') or 'Не указано'
                location = f"{theatre_name}, {hall_name}" if theatre_name != 'Не указано' or hall_name != 'Не указано' else 'Не указано'
                production_title = performance.get('production_title', 'Не указано') or 'Не указано'
                
                row = [
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(self.format_datetime_for_display(performance.get('datetime')) or 'Не указано', self.table_cell_center_style),
                    Paragraph(location, self.table_cell_style),
                    Paragraph(production_title, self.table_cell_style)
                ]
                data.append(row)
        
        col_widths = [0.5*inch, 1.2*inch, 2.0*inch, 2.8*inch]
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#B8865B')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FFF8F0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        return table

    def create_plays_table(self):
        """Создание таблицы пьес"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("Название", self.table_header_style),
            Paragraph("Жанр", self.table_header_style),
            Paragraph("Год", self.table_header_style)
        ]
        data = [header_data]
        
        plays = self.plays_data
        if not plays:
            no_data_row = [
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_center_style)
            ]
            data.append(no_data_row)
        else:
            for idx, play in enumerate(plays, start=1):
                title = play.get('title', 'Не указано') or 'Не указано'
                genre = play.get('genre', 'Не указано') or 'Не указано'
                year = str(play.get('year_written', '')) if play.get('year_written') else 'Не указано'
                
                row = [
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(title, self.table_cell_style),
                    Paragraph(genre, self.table_cell_style),
                    Paragraph(year, self.table_cell_center_style)
                ]
                data.append(row)
        
        col_widths = [0.5*inch, 3.0*inch, 1.5*inch, 0.7*inch]
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B7A9E')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F0FA')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        return table

    def create_authors_table(self):
        """Создание таблицы авторов с полным отображением биографии"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("ФИО", self.table_header_style),
            Paragraph("Биография", self.table_header_style)
        ]
        data = [header_data]
        
        authors = self.authors_data
        if not authors:
            no_data_row = [
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style)
            ]
            data.append(no_data_row)
        else:
            for idx, author in enumerate(authors, start=1):
                full_name = author.get('full_name', '') or 'Не указано'
                bio = author.get('biography', '') or 'Не указано'
                
                # Экранируем HTML символы для Paragraph
                full_name_escaped = full_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                bio_escaped = bio.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                row = [
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(full_name_escaped, self.table_cell_style),
                    Paragraph(bio_escaped, self.table_cell_style)
                ]
                data.append(row)
        
        col_widths = [0.5*inch, 1.5*inch, 4.5*inch]
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5F9EA0')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F0F8F8')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        return table

    def create_directors_table(self):
        """Создание таблицы режиссеров с полным отображением биографии"""
        header_data = [
            Paragraph("№", self.table_header_style),
            Paragraph("ФИО", self.table_header_style),
            Paragraph("Биография", self.table_header_style)
        ]
        data = [header_data]
        
        directors = self.directors_data
        if not directors:
            no_data_row = [
                Paragraph("Нет данных", self.table_cell_center_style),
                Paragraph("Нет данных", self.table_cell_style),
                Paragraph("Нет данных", self.table_cell_style)
            ]
            data.append(no_data_row)
        else:
            for idx, director in enumerate(directors, start=1):
                full_name = director.get('full_name', '') or 'Не указано'
                bio = director.get('biography', '') or 'Не указано'
                
                # Экранируем HTML символы для Paragraph
                full_name_escaped = full_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                bio_escaped = bio.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                row = [
                    Paragraph(str(idx), self.table_cell_center_style),
                    Paragraph(full_name_escaped, self.table_cell_style),
                    Paragraph(bio_escaped, self.table_cell_style)
                ]
                data.append(row)
        
        col_widths = [0.5*inch, 1.5*inch, 4.5*inch]
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9370DB')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F0FF')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        return table

async def init_database():
    """Инициализация базы данных для формирования отчетов."""
    global db_manager
    
    try:
        loop = asyncio.get_event_loop()
        db_manager = DatabaseManager(loop)
        success = await db_manager.init_pool()
        if success:
            logging.info("База данных успешно инициализирована для экспорта")
            return True
        logging.error("Не удалось инициализировать базу данных")
        return False
    except Exception as e:
        logging.error(f"Ошибка инициализации базы данных: {e}")
        return False

async def main():
    """Основная функция генерации отчетов"""
    
    # Инициализация базы данных
    success = await init_database()
    if not success:
        logging.error("Не удалось инициализировать базу данных. Экспорт невозможен.")
        return
    
    # Создаем экземпляры отчетов
    statistical_report = StatisticalReport()
    detailed_report = DetailedReport()
    
    # Генерируем отчеты
    logging.info("Начало генерации статистического отчета...")
    stat_success = await statistical_report.generate_report()
    
    logging.info("Начало генерации детального отчета...")
    det_success = await detailed_report.generate_report()
    
    # Закрываем соединение с БД
    if db_manager:
        await db_manager.close_pool()
    
    # Результаты
    if stat_success and det_success:
        logging.info("Оба отчета успешно сгенерированы!")
    elif stat_success:
        logging.info("Статистический отчет успешно сгенерирован!")
    elif det_success:
        logging.info("Детальный отчет успешно сгенерирован!")
    else:
        logging.error("Не удалось сгенерировать ни один отчет")

def run_export():
    """Запуск экспорта в отдельном потоке событий"""
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Ошибка при выполнении экспорта: {e}")
    finally:
        # Даем время на завершение операций
        import time
        time.sleep(2)
        logging.info("Экспорт завершен. Файлы сохранены в текущей директории.")

# Защита от прямого запуска - файл должен использоваться только через main.py
if __name__ == "__main__":
    print("=" * 60)
    print("ВНИМАНИЕ: Этот файл нельзя запускать отдельно!")
    print("Используйте функцию экспорта из основного приложения (main.py)")
    print("=" * 60)
    sys.exit(1)
    print("Запуск генерации PDF отчетов...")
    print("Пожалуйста, подождите...")
    
    # Запускаем экспорт
    run_export()
    
    print("Генерация отчетов завершена!")