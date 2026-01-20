"""
Модуль для генерации Excel отчетов из данных театральной системы.

Используемые библиотеки:
- asyncio: асинхронное выполнение запросов к базе данных и параллельная загрузка данных
- aiomysql: асинхронный драйвер для работы с MySQL базой данных
  - aiomysql.create_pool: создание пула соединений для эффективной работы с БД
  - aiomysql.DictCursor: курсор, возвращающий результаты в виде словарей
- xlsxwriter: создание Excel файлов (.xlsx) с форматированием, диаграммами и стилями
- datetime: форматирование дат в отчетах
"""
import asyncio
import aiomysql
import xlsxwriter
from datetime import datetime
from typing import Optional
import logging
import sys
import os

# Универсальный импорт конфигурации - работает и как модуль, и при прямом запуске
try:
    # Пытаемся импортировать как модуль (относительный импорт)
    from config.database import DB_CONFIG
except ImportError:
    # Если не работает, пытаемся абсолютный импорт
    try:
        from config.database import DB_CONFIG
    except ImportError:
        # Если и это не работает, добавляем родительскую директорию в путь
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config.database import DB_CONFIG

_POOL = None

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def get_pool():
    """Возвращает общий пул соединений aiomysql."""
    global _POOL
    if _POOL is None:
        _POOL = await aiomysql.create_pool(**DB_CONFIG)
        logging.info("Пул соединений с базой данных создан")
    return _POOL


async def close_pool():
    """Закрывает пул соединений, если он существует."""
    global _POOL
    if _POOL:
        logging.info("Закрытие пула соединений...")
        _POOL.close()
        await _POOL.wait_closed()
        _POOL = None
        logging.info("Пул соединений закрыт")


async def get_data_from_db(query, params=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params or ())
            return await cursor.fetchall()

async def get_all_productions_data():
    query = """
        SELECT 
            p.id,
            p.title AS production_title,
            p.production_date,
            p.description,
            pl.title AS play_title,
            pl.genre,
            pl.year_written,
            d.full_name AS director_name,
            (SELECT a.full_name FROM author_play ap2 
             JOIN author a ON ap2.author_id = a.id 
             WHERE ap2.play_id = pl.id LIMIT 1) AS author_name,
            (SELECT t.name FROM performance perf2 
             JOIN location loc2 ON perf2.location_id = loc2.id 
             JOIN theatre t ON loc2.theatre_id = t.id 
             WHERE perf2.production_id = p.id LIMIT 1) AS theatre_name,
            (SELECT t.city FROM performance perf3 
             JOIN location loc3 ON perf3.location_id = loc3.id 
             JOIN theatre t ON loc3.theatre_id = t.id 
             WHERE perf3.production_id = p.id LIMIT 1) AS city,
            (SELECT COUNT(*) FROM performance WHERE production_id = p.id) AS performances_count,
            (SELECT COUNT(*) FROM rehearsal WHERE production_id = p.id) AS rehearsals_count,
            (SELECT COUNT(DISTINCT actor_id) FROM actor_production WHERE production_id = p.id) AS actors_count
        FROM production p
        LEFT JOIN play pl ON p.play_id = pl.id
        LEFT JOIN director d ON p.director_id = d.id
        ORDER BY p.production_date DESC, p.title
    """
    return await get_data_from_db(query)

async def get_analytics_data():
    analytics = {}
    
    query_genres = """
        SELECT 
            pl.genre,
            COUNT(DISTINCT p.id) AS productions_count,
            COUNT(DISTINCT perf.id) AS performances_count,
            COUNT(DISTINCT ar.actor_id) AS actors_count
        FROM play pl
        LEFT JOIN production p ON pl.id = p.play_id
        LEFT JOIN performance perf ON p.id = perf.production_id
        LEFT JOIN actor_production ar ON p.id = ar.production_id
        WHERE pl.genre IS NOT NULL
        GROUP BY pl.genre
        ORDER BY productions_count DESC
    """
    analytics['genres'] = await get_data_from_db(query_genres)
    
    query_theatres = """
        SELECT 
            t.name AS theatre_name,
            t.city,
            COUNT(DISTINCT loc.id) AS locations_count,
            COUNT(DISTINCT perf.id) AS performances_count,
            SUM(loc.capacity) AS total_capacity
        FROM theatre t
        LEFT JOIN location loc ON t.id = loc.theatre_id
        LEFT JOIN performance perf ON loc.id = perf.location_id
        GROUP BY t.id, t.name, t.city
        ORDER BY performances_count DESC
    """
    analytics['theatres'] = await get_data_from_db(query_theatres)
    
    query_directors = """
        SELECT 
            d.full_name AS director_name,
            COUNT(DISTINCT p.id) AS productions_count,
            COUNT(DISTINCT perf.id) AS performances_count
        FROM director d
        LEFT JOIN production p ON d.id = p.director_id
        LEFT JOIN performance perf ON p.id = perf.production_id
        GROUP BY d.id, d.full_name
        ORDER BY productions_count DESC
    """
    analytics['directors'] = await get_data_from_db(query_directors)
    
    query_actors = """
        SELECT 
            a.full_name AS actor_name,
            COUNT(DISTINCT ap.production_id) AS productions_count,
            COUNT(DISTINCT ar.rehearsal_id) AS rehearsals_count
        FROM actor a
        LEFT JOIN actor_production ap ON a.id = ap.actor_id
        LEFT JOIN actor_rehearsal ar ON a.id = ar.actor_id
        GROUP BY a.id, a.full_name
        ORDER BY productions_count DESC
    """
    analytics['actors'] = await get_data_from_db(query_actors)
    
    query_rehearsals_by_month = """
        SELECT 
            DATE_FORMAT(r.datetime, '%%Y-%%m') AS month,
            COUNT(r.id) AS rehearsals_count,
            COUNT(DISTINCT r.production_id) AS productions_count
        FROM rehearsal r
        GROUP BY DATE_FORMAT(r.datetime, '%%Y-%%m')
        ORDER BY month DESC
    """
    analytics['rehearsals_by_month'] = await get_data_from_db(query_rehearsals_by_month)
    
    return analytics


async def fetch_report_data():
    """Параллельная загрузка всех данных отчета."""
    productions_task = asyncio.create_task(get_all_productions_data())
    analytics_task = asyncio.create_task(get_analytics_data())
    return await asyncio.gather(productions_task, analytics_task)

def create_report(filepath=None):
    """
    Создает Excel отчет с данными театральной системы.
    Исправлена проблема с закрытием event loop - теперь пул закрывается корректно.
    
    Args:
        filepath: Путь для сохранения отчета. Если None, используется путь по умолчанию.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    logging.info("Подключение к базе данных...")
    productions_data = None
    analytics_data = None
    
    try:
        productions_data, analytics_data = loop.run_until_complete(fetch_report_data())
        logging.info("Данные успешно загружены из базы данных")
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных: {e}")
        raise
    finally:
        # Закрываем пул соединений перед закрытием event loop
        try:
            # Закрываем пул в event loop
            if _POOL is not None:
                loop.run_until_complete(close_pool())
        except Exception as e:
            logging.warning(f"Предупреждение при закрытии пула: {e}")
        finally:
            # Даем время на завершение всех операций с соединениями
            import time
            time.sleep(0.2)
            
            # Закрываем event loop только после полного завершения всех операций
            try:
                # Отменяем все незавершенные задачи
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                if pending:
                    for task in pending:
                        task.cancel()
                    # Ждем завершения отмененных задач с таймаутом
                    try:
                        loop.run_until_complete(asyncio.wait_for(
                            asyncio.gather(*pending, return_exceptions=True),
                            timeout=1.0
                        ))
                    except asyncio.TimeoutError:
                        pass
            except Exception as e:
                logging.warning(f"Ошибка при отмене задач: {e}")
            finally:
                # Закрываем event loop
                try:
                    if not loop.is_closed():
                        loop.close()
                        logging.info("Event loop закрыт")
                except Exception as e:
                    logging.warning(f"Ошибка при закрытии event loop: {e}")
    
    if not filepath:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f'Театральная_система_отчет_{timestamp}.xlsx'
    
    # Убеждаемся, что директория существует
    directory = os.path.dirname(filepath) if os.path.dirname(filepath) else os.getcwd()
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    filename = filepath
    workbook = xlsxwriter.Workbook(filename)
    
    # Форматы
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'fg_color': '#FF6B35',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    header_format = workbook.add_format({
        'bold': True,
        'font_size': 11,
        'fg_color': '#FFE0B2',
        'font_color': '#BF360C',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Правильные числовые форматы
    id_format = workbook.add_format({'num_format': '0', 'border': 1, 'align': 'center'})
    date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'border': 1, 'align': 'center'})
    number_format = workbook.add_format({'num_format': '#,##0', 'border': 1, 'align': 'center'})
    year_format = workbook.add_format({'num_format': '0', 'border': 1, 'align': 'center'})
    text_format = workbook.add_format({'border': 1, 'valign': 'top'})
    center_format = workbook.add_format({'align': 'center', 'border': 1, 'valign': 'vcenter'})
    bold_format = workbook.add_format({'bold': True, 'border': 1})
    decimal_format = workbook.add_format({'num_format': '0.00', 'border': 1, 'align': 'center'})
    
    # ЛИСТ 1: ДАННЫЕ ПРОЕКТА
    worksheet_data = workbook.add_worksheet('Данные проекта')
    
    worksheet_data.merge_range('A1:M1', 'ОТЧЕТ ПО ПРОЕКТУ ТЕАТРАЛЬНАЯ СИСТЕМА', title_format)
    worksheet_data.merge_range('A2:M2', 'Студент:Попов Никита Михайлович', header_format)
    worksheet_data.set_row(0, 40)
    worksheet_data.set_row(1, 25) 
    
    headers = [
        '№', 'Название постановки', 'Дата постановки', 'Пьеса', 'Жанр', 
        'Год написания', 'Режиссер', 'Автор', 'Театр', 'Город',
        'Кол-во спектаклей', 'Кол-во репетиций', 'Кол-во актеров'
    ]
    
    for col, header in enumerate(headers):
        worksheet_data.write(3, col, header, header_format)

    for row_idx, record in enumerate(productions_data, start=4):
        worksheet_data.write_number(row_idx, 0, row_idx - 3, id_format) 
        worksheet_data.write(row_idx, 1, record['production_title'] or '', text_format) 
        
        if record['production_date']:
            worksheet_data.write_datetime(row_idx, 2, record['production_date'], date_format)  
        else:
            worksheet_data.write(row_idx, 2, '', center_format)
        
        worksheet_data.write(row_idx, 3, record['play_title'] or '', text_format) 
        worksheet_data.write(row_idx, 4, record['genre'] or '', center_format) 
        worksheet_data.write_number(row_idx, 5, record['year_written'] or 0, year_format) 
        worksheet_data.write(row_idx, 6, record['director_name'] or '', text_format) 
        worksheet_data.write(row_idx, 7, record['author_name'] or '', text_format) 
        worksheet_data.write(row_idx, 8, record['theatre_name'] or '', text_format)  
        worksheet_data.write(row_idx, 9, record['city'] or '', center_format)  
        worksheet_data.write_number(row_idx, 10, record['performances_count'] or 0, number_format) 
        worksheet_data.write_number(row_idx, 11, record['rehearsals_count'] or 0, number_format) 
        worksheet_data.write_number(row_idx, 12, record['actors_count'] or 0, number_format)  

    column_widths = [6, 30, 15, 25, 15, 12, 25, 25, 25, 15, 15, 15, 15]
    for col, width in enumerate(column_widths):
        worksheet_data.set_column(col, col, width)


    if productions_data:
        worksheet_data.autofilter(3, 0, len(productions_data) + 2, len(headers) - 1)


    worksheet_data.freeze_panes(4, 0)

    
    # ЛИСТ 2: АНАЛИТИКА
    worksheet_analytics = workbook.add_worksheet('Аналитика')
    
    worksheet_analytics.merge_range('A1:F1', 'АНАЛИТИКА ДАННЫХ', title_format)
    worksheet_analytics.set_row(0, 40)
    
    row = 4
    
    # 1. Статистика по жанрам
    worksheet_analytics.merge_range(f'A{row}:D{row}', 'Статистика по жанрам пьес', title_format)
    row += 1
    
    genre_headers = ['Жанр', 'Кол-во постановок', 'Кол-во спектаклей', 'Кол-во актеров']
    for col, header in enumerate(genre_headers):
        worksheet_analytics.write(row, col, header, header_format)
    row += 1
    
    genre_table_start = row if analytics_data['genres'] else None
    for record in analytics_data['genres']:
        worksheet_analytics.write(row, 0, record['genre'] or 'Не указан', text_format)
        worksheet_analytics.write_number(row, 1, record['productions_count'] or 0, number_format)
        worksheet_analytics.write_number(row, 2, record['performances_count'] or 0, number_format)
        worksheet_analytics.write_number(row, 3, record['actors_count'] or 0, number_format)
        row += 1
    genre_table_end = (row - 1) if genre_table_start is not None else None
    
    # Расчетные показатели для жанров
    row += 1
    worksheet_analytics.write(row, 0, 'Среднее кол-во постановок:', bold_format)
    if analytics_data['genres']:
        avg_productions = sum(r['productions_count'] or 0 for r in analytics_data['genres']) / len(analytics_data['genres'])
        worksheet_analytics.write(row, 1, avg_productions, decimal_format)
    
    row += 1
    worksheet_analytics.write(row, 0, 'Всего постановок:', bold_format)
    total_productions = sum(r['productions_count'] or 0 for r in analytics_data['genres'])
    worksheet_analytics.write_number(row, 1, total_productions, number_format)
    
    row += 3
    
    # 2. Статистика по театрам
    worksheet_analytics.merge_range(f'A{row}:E{row}', 'Статистика по театрам', title_format)
    row += 1
    
    theatre_headers = ['Театр', 'Город', 'Кол-во залов', 'Кол-во спектаклей', 'Общая вместимость']
    for col, header in enumerate(theatre_headers):
        worksheet_analytics.write(row, col, header, header_format)
    row += 1
    
    theatre_table_start = row if analytics_data['theatres'] else None
    for record in analytics_data['theatres']:
        worksheet_analytics.write(row, 0, record['theatre_name'] or '', text_format)
        worksheet_analytics.write(row, 1, record['city'] or '', center_format)
        worksheet_analytics.write_number(row, 2, record['locations_count'] or 0, number_format)
        worksheet_analytics.write_number(row, 3, record['performances_count'] or 0, number_format)
        worksheet_analytics.write_number(row, 4, record['total_capacity'] or 0, number_format)
        row += 1
    theatre_table_end = (row - 1) if theatre_table_start is not None else None
    
    row += 3
    
    # 3. Диаграмма 1: Столбчатая диаграмма по жанрам
    if genre_table_start is not None and genre_table_end is not None and genre_table_end >= genre_table_start:
        chart1 = workbook.add_chart({'type': 'column'})
        excel_start = genre_table_start + 1
        excel_end = genre_table_end + 1
        
        chart1.add_series({
            'name': 'Количество постановок',
            'categories': f'=Аналитика!$A${excel_start}:$A${excel_end}',
            'values': f'=Аналитика!$B${excel_start}:$B${excel_end}',
        })
        chart1.set_title({'name': 'Количество постановок по жанрам'})
        chart1.set_x_axis({'name': 'Жанр'})
        chart1.set_y_axis({'name': 'Количество'})
        chart1.set_style(10)
        chart1.set_legend({'none': True})
        worksheet_analytics.insert_chart(row, 0, chart1)
        row += 20

    
    # 4. Диаграмма 2: Круговая диаграмма по театрам
    if theatre_table_start is not None and theatre_table_end is not None and theatre_table_end >= theatre_table_start:
        chart2 = workbook.add_chart({'type': 'pie'})
        theatre_excel_start = theatre_table_start + 1
        theatre_excel_end = theatre_table_end + 1
        chart2.add_series({
            'name': 'Спектакли по театрам',
            'categories': f'=Аналитика!$A${theatre_excel_start}:$A${theatre_excel_end}',
            'values': f'=Аналитика!$D${theatre_excel_start}:$D${theatre_excel_end}',
        })
        chart2.set_title({'name': 'Распределение спектаклей по театрам'})
        chart2.set_style(10)
        worksheet_analytics.insert_chart(row, 0, chart2)
        row += 20
    # 5. Блок с расчетными показателями
    row += 2
    worksheet_analytics.merge_range(f'A{row}:B{row}', 'РАСЧЕТНЫЕ ПОКАЗАТЕЛИ', title_format)
    
    # Общие показатели
    total_actors = len(analytics_data['actors'])
    total_directors = len(analytics_data['directors'])
    total_theatres = len(analytics_data['theatres'])
    total_performances = sum(r['performances_count'] or 0 for r in analytics_data['theatres'])
    
    metrics = [
        ['Всего актеров в базе:', total_actors],
        ['Всего режиссеров:', total_directors],
        ['Всего театров:', total_theatres],
        ['Всего спектаклей:', total_performances],
    ]
    
    if analytics_data['genres']:
        avg_per_genre = total_productions / len(analytics_data['genres'])
        metrics.append(['Среднее постановок на жанр:', avg_per_genre])
    
    if analytics_data['theatres']:
        avg_per_theatre = total_performances / total_theatres if total_theatres > 0 else 0
        metrics.append(['Среднее спектаклей на театр:', avg_per_theatre])
    
    for metric_name, metric_value in metrics:
        worksheet_analytics.write(row, 0, metric_name, bold_format)
        if isinstance(metric_value, int):
            worksheet_analytics.write_number(row, 1, metric_value, number_format)
        else:
            worksheet_analytics.write(row, 1, metric_value, decimal_format)
        row += 1
    
    # 6. Выводы по аналитике
    row += 2
    worksheet_analytics.merge_range(f'A{row}:B{row}', 'ВЫВОДЫ ПО АНАЛИТИКЕ', title_format)
    row += 1
    
    conclusions = [
        f'1. В базе данных представлено {total_productions} постановок по {len(analytics_data["genres"])} различным жанрам.',
        f'2. Наиболее активными являются театры в городе Москва (всего {total_theatres} театров).',
        f'3. В системе зарегистрировано {total_actors} актеров, участвующих в постановках.',
        f'4. Всего запланировано {total_performances} спектаклей.',
    ]
    
    if analytics_data['genres']:
        top_genre = max(analytics_data['genres'], key=lambda x: x['productions_count'] or 0)
        conclusions.append(f'5. Наиболее популярный жанр: {top_genre["genre"]} ({top_genre["productions_count"]} постановок).')
    
    for conclusion in conclusions:
        worksheet_analytics.merge_range(row, 0, row, 3, conclusion, text_format)
        row += 1
    
    # Устанавливаем ширину колонок для листа аналитики
    worksheet_analytics.set_column('A:A', 30)
    worksheet_analytics.set_column('B:B', 20)
    worksheet_analytics.set_column('C:C', 20)
    worksheet_analytics.set_column('D:D', 20)
    worksheet_analytics.set_column('E:E', 20)
    
    # ЛИСТ 3: ВИЗУАЛИЗАЦИЯ 
    worksheet_viz = workbook.add_worksheet('Визуализация')
    
    worksheet_viz.merge_range('A1:F1', 'ВИЗУАЛИЗАЦИЯ ДАННЫХ', title_format)
    worksheet_viz.set_row(0, 40)
    
    row = 3
    
    # 1. Линейный график: Репетиции по месяцам
    if analytics_data['rehearsals_by_month']:
        worksheet_viz.merge_range(f'A{row}:C{row}', 'Расписание репетиций по месяцам', title_format)
        row += 1
        
        month_headers = ['Месяц', 'Кол-во репетиций', 'Кол-во постановок']
        for col, header in enumerate(month_headers):
            worksheet_viz.write(row, col, header, header_format)
        row += 1
        
        for record in analytics_data['rehearsals_by_month']:
            worksheet_viz.write(row, 0, record['month'], center_format)
            worksheet_viz.write_number(row, 1, record['rehearsals_count'] or 0, number_format)
            worksheet_viz.write_number(row, 2, record['productions_count'] or 0, number_format)
            row += 1
        
        # Линейный график
        chart3 = workbook.add_chart({'type': 'line'})
        row+=1
        chart3.add_series({
            'name': 'Репетиции',
            'categories': f'=Визуализация!$A${row - len(analytics_data["rehearsals_by_month"])}:$A${row-1}',
            'values': f'=Визуализация!$B${row - len(analytics_data["rehearsals_by_month"])}:$B${row-1}',
        })
        chart3.set_title({'name': 'Динамика репетиций по месяцам'})
        chart3.set_x_axis({'name': 'Месяц'})
        chart3.set_y_axis({'name': 'Количество репетиций'})
        chart3.set_style(10)
        worksheet_viz.insert_chart(row, 0, chart3)
        row += 20
    
    # 2. Гистограмма: Активность режиссеров
    if analytics_data['directors']:
        row += 2
        worksheet_viz.merge_range(f'A{row}:C{row}', 'Активность режиссеров', title_format)
        row += 1
        
        director_headers = ['Режиссер', 'Кол-во постановок', 'Кол-во спектаклей']
        for col, header in enumerate(director_headers):
            worksheet_viz.write(row, col, header, header_format)
        row += 1
        
        for record in analytics_data['directors'][:10]:  # Топ-10
            worksheet_viz.write(row, 0, record['director_name'] or '', text_format)
            worksheet_viz.write_number(row, 1, record['productions_count'] or 0, number_format)
            worksheet_viz.write_number(row, 2, record['performances_count'] or 0, number_format)
            row += 1
        
        # Гистограмма
        row+=1
        chart4 = workbook.add_chart({'type': 'column'})
        director_start_row = row - min(10, len(analytics_data['directors']))
        chart4.add_series({
            'name': 'Постановки',
            'categories': f'=Визуализация!$A${director_start_row}:$A${row}',
            'values': f'=Визуализация!$B${director_start_row}:$B${row}',
        })
        chart4.add_series({
            'name': 'Спектакли',
            'categories': f'=Визуализация!$A${director_start_row}:$A${row - 1}',
            'values': f'=Визуализация!$C${director_start_row}:$C${row - 1}',
        })
        chart4.set_title({'name': 'Активность режиссеров'})
        chart4.set_x_axis({'name': 'Режиссер'})
        chart4.set_y_axis({'name': 'Количество'})
        chart4.set_style(10)
        worksheet_viz.insert_chart(row, 0, chart4)
        row += 20
    
    # 3. Инфографика основных показателей
    row += 2
    worksheet_viz.merge_range(f'A{row}:B{row}', 'ИНФОГРАФИКА ОСНОВНЫХ ПОКАЗАТЕЛЕЙ', title_format)
    row += 1
    
    # Создаем таблицу с ключевыми показателями
    info_headers = ['Показатель', 'Значение', 'Описание']
    for col, header in enumerate(info_headers):
        worksheet_viz.write(row, col, header, header_format)
    row += 1
    
    info_data = [
        ['Всего постановок', total_productions, 'Общее количество постановок в базе'],
        ['Всего спектаклей', total_performances, 'Запланированных спектаклей'],
        ['Всего актеров', total_actors, 'Актеров участвует в постановках'],
        ['Всего режиссеров', total_directors, 'Режиссеров в базе'],
        ['Всего театров', total_theatres, 'Театров в системе'],
    ]
    
    if analytics_data['genres']:
        info_data.append(['Жанров пьес', len(analytics_data['genres']), 'Различных жанров представлено'])
    
    for info_row in info_data:
        worksheet_viz.write(row, 0, info_row[0], bold_format)
        worksheet_viz.write_number(row, 1, info_row[1], number_format)
        worksheet_viz.write(row, 2, info_row[2], text_format)
        row += 1
    
    # Устанавливаем ширину колонок
    worksheet_viz.set_column('A:A', 30)
    worksheet_viz.set_column('B:B', 20)
    worksheet_viz.set_column('C:C', 40)
    
    workbook.close()
    
    logging.info(f"Отчет успешно создан: {filename}")
    print(f"Отчет успешно создан: {filename}")
    return filename


def create_report_with_path(filepath: str) -> Optional[str]:
    """
    Создает Excel отчет с указанным путем.
    
    Args:
        filepath: Полный путь для сохранения отчета
    
    Returns:
        Путь к созданному файлу или None при ошибке
    """
    return create_report(filepath)


# Защита от прямого запуска - файл должен использоваться только через main.py
if __name__ == '__main__':
    print("=" * 60)
    print("ВНИМАНИЕ: Этот файл нельзя запускать отдельно!")
    print("Используйте функцию экспорта из основного приложения (main.py)")
    print("=" * 60)
    sys.exit(1)
