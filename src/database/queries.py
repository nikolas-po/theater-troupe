"""
SQL запросы для работы с базой данных.
Содержит часто используемые запросы для оптимизации и переиспользования.
"""
from typing import Dict, Any, Optional, List


class Queries:
    """Класс с часто используемыми SQL запросами"""
    
    # Запросы для получения статистики
    GET_TOTAL_COUNT = "SELECT COUNT(*) as total FROM {table}"
    
    GET_ACTORS_WITH_STATS = """
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
    
    GET_PRODUCTIONS_WITH_DETAILS = """
        SELECT p.id, p.title, p.production_date, 
            pl.id as play_id, pl.title as play_title, pl.genre,
            d.id as director_id, d.full_name as director_name
        FROM production p
        JOIN play pl ON p.play_id = pl.id
        JOIN director d ON p.director_id = d.id
        ORDER BY p.production_date DESC
    """
    
    GET_REHEARSALS_WITH_DETAILS = """
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
    
    GET_PERFORMANCES_WITH_DETAILS = """
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
    
    # Статистические запросы
    GET_REHEARSALS_BY_MONTH = """
        SELECT 
            DATE_FORMAT(datetime, '%%Y-%%m') as month,
            COUNT(*) as count
        FROM rehearsal 
        WHERE datetime >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(datetime, '%%Y-%%m')
        ORDER BY month DESC
    """
    
    GET_PLAYS_BY_GENRE = """
        SELECT 
            genre,
            COUNT(*) as count
        FROM play 
        WHERE genre IS NOT NULL AND genre != ''
        GROUP BY genre
        ORDER BY count DESC
    """
    
    GET_PRODUCTIONS_BY_THEATRE = """
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
    
    GET_PRODUCTIONS_BY_DIRECTOR = """
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
    
    GET_TOP_ACTORS_BY_REHEARSALS = """
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
    
    @staticmethod
    def format_query(query: str, **kwargs) -> str:
        """
        Форматирует SQL запрос с подстановкой параметров.
        
        Args:
            query: SQL запрос с плейсхолдерами {param}
            **kwargs: Параметры для подстановки
        
        Returns:
            Отформатированный запрос
        """
        return query.format(**kwargs)
