"""
Модуль управления базой данных.
"""
import asyncio
import logging
import aiomysql
from config.database import DB_CONFIG
from src.utils.validators import (
    validate_full_name, validate_title, validate_year,
    validate_date, validate_datetime, validate_capacity
)


class DatabaseManager:
    TABLE_CONFIG = {
        'actors': {
            'from': 'actor a',
            'select': 'a.*',
            'orderable': {
                'id': 'a.id',
                'full_name': 'a.full_name',
                'experience': 'a.experience',
            },
            'default_sort': 'id',
            'searchable': ['a.full_name', 'a.experience'],
        },
        'authors': {
            'from': 'author a',
            'select': 'a.*',
            'orderable': {
                'id': 'a.id',
                'full_name': 'a.full_name',
                'biography': 'a.biography',
            },
            'default_sort': 'id',
            'searchable': ['a.full_name', 'a.biography'],
        },
        'directors': {
            'from': 'director d',
            'select': 'd.*',
            'orderable': {
                'id': 'd.id',
                'full_name': 'd.full_name',
                'biography': 'd.biography',
            },
            'default_sort': 'id',
            'searchable': ['d.full_name', 'd.biography'],
        },
        'plays': {
            'from': 'play p',
            'select': 'p.*',
            'orderable': {
                'id': 'p.id',
                'title': 'p.title',
                'genre': 'p.genre',
                'year_written': 'p.year_written',
                'description': 'p.description',
            },
            'default_sort': 'id',
            'searchable': ['p.title', 'p.genre', 'p.description'],
        },
        'productions': {
            'from': 'production p',
            'select': 'p.*',
            'orderable': {
                'id': 'p.id',
                'title': 'p.title',
                'production_date': 'p.production_date',
                'description': 'p.description',
            },
            'default_sort': 'id',
            'searchable': ['p.title', 'p.description'],
        },
        'performances': {
            'from': 'performance p',
            'select': 'p.*, t.name AS theatre_name, l.hall_name, pr.title AS production_title',
            'joins': 'JOIN location l ON p.location_id = l.id '
                     'JOIN theatre t ON l.theatre_id = t.id '
                     'JOIN production pr ON p.production_id = pr.id',
            'orderable': {
                'id': 'p.id',
                'datetime': 'p.datetime',
            },
            'default_sort': 'id',
            'searchable': ['CAST(p.datetime AS CHAR)', 't.name', 'l.hall_name', 'pr.title'],
        },
        'rehearsals': {
            'from': 'rehearsal r',
            'select': 'r.*, t.name AS theatre_name, l.hall_name, pr.title AS production_title',
            'joins': 'JOIN location l ON r.location_id = l.id '
                     'JOIN theatre t ON l.theatre_id = t.id '
                     'JOIN production pr ON r.production_id = pr.id',
            'orderable': {
                'id': 'r.id',
                'datetime': 'r.datetime',
            },
            'default_sort': 'id',
            'searchable': ['CAST(r.datetime AS CHAR)', 't.name', 'l.hall_name', 'pr.title'],
        },
        'roles': {
            'from': 'role r',
            'select': 'r.*, p.title AS play_title',
            'joins': 'LEFT JOIN play p ON r.play_id = p.id',
            'orderable': {
                'id': 'r.id',
                'title': 'r.title',
                'description': 'r.description',
            },
            'default_sort': 'id',
            'searchable': ['r.title', 'r.description', 'p.title'],
        },
        'theatres': {
            'from': 'theatre t',
            'select': 't.*',
            'orderable': {
                'id': 't.id',
                'name': 't.name',
                'city': 't.city',
                'street': 't.street',
                'house_number': 't.house_number',
                'postal_code': 't.postal_code',
            },
            'default_sort': 'name',
            'searchable': ['t.name', 't.city', 't.street', 't.house_number', 't.postal_code'],
        },
        'locations': {
            'from': 'location l',
            'select': 'l.*, t.name AS theatre_name, t.city, t.street, t.house_number, t.postal_code',
            'joins': 'JOIN theatre t ON l.theatre_id = t.id',
            'orderable': {
                'id': 'l.id',
                'theatre_name': 't.name',
                'hall_name': 'l.hall_name',
                'capacity': 'l.capacity',
            },
            'default_sort': 'hall_name',
            'searchable': ['t.name', 'l.hall_name', 't.city', 't.street', 't.house_number', 't.postal_code'],
        },
    }

    def __init__(self, loop):
        self.pool = None
        self.loop = loop
        self._lock = asyncio.Lock()

    def _get_table_config(self, key):
        config = self.TABLE_CONFIG.get(key)
        if not config:
            raise ValueError(f"Неизвестная конфигурация таблицы: {key}")
        return config

    def _resolve_sort_column(self, config, sort_column):
        orderable = config['orderable']
        fallback = config['default_sort']
        column_key = sort_column if sort_column in orderable else fallback
        return orderable[column_key]

    def _build_base_query(self, config):
        query = f"SELECT {config['select']} FROM {config['from']}"
        joins = config.get('joins')
        if joins:
            query = f"{query} {joins}"
        return query

    async def _select_all(self, key, sort_column=None, sort_ascending=True, force_refresh=False):
        config = self._get_table_config(key)
        order_expr = self._resolve_sort_column(config, sort_column or config['default_sort'])
        direction = 'ASC' if sort_ascending else 'DESC'
        query = f"{self._build_base_query(config)} ORDER BY {order_expr} {direction}"
        return await self.execute_query(query, force_refresh=force_refresh)

    async def _search_records(self, key, search_text, sort_column=None, sort_ascending=True, force_refresh=False):
        if not search_text:
            return await self._select_all(key, sort_column, sort_ascending, force_refresh)
        config = self._get_table_config(key)
        pattern = f"%{search_text}%"
        conditions = [f"{expr} LIKE %s" for expr in config['searchable']]
        where_clause = " OR ".join(conditions)
        order_expr = self._resolve_sort_column(config, sort_column or config['default_sort'])
        direction = 'ASC' if sort_ascending else 'DESC'
        query = (
            f"{self._build_base_query(config)} "
            f"WHERE {where_clause} "
            f"ORDER BY {order_expr} {direction}"
        )
        params = tuple(pattern for _ in config['searchable'])
        return await self.execute_query(query, params, force_refresh=force_refresh)

    async def _get_unique_values(self, table, column):
        query = f"""
            SELECT DISTINCT {column} AS value
            FROM {table}
            WHERE {column} IS NOT NULL AND {column} != ''
            ORDER BY value
        """
        try:
            rows = await self.execute_query(query)
            return [row['value'] for row in rows] if rows else []
        except Exception as exc:
            logging.error(f"Ошибка получения уникальных значений из {table}: {exc}")
            return []
    
    async def init_pool(self):
        try:
            self.pool = await aiomysql.create_pool(**DB_CONFIG, loop=self.loop)
            logging.warning("Пул соединений с базой данных инициализирован")
            return True
        except Exception as e:
            logging.error(f"Ошибка инициализации пула: {e}")
            return False
    
    async def close_pool(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            # Не логируем закрытие пула (слишком часто)
    
    async def execute_query(self, query, args=None, max_retries=3, force_refresh=False):
        """
        Выполняет SQL запрос к базе данных с повторными попытками при ошибках.
        
        Логирование:
        - DEBUG: выполнение SELECT запросов
        - INFO: выполнение INSERT/UPDATE/DELETE операций
        - ERROR: ошибки выполнения запросов
        """
        if not self.pool:
            logging.error("Попытка выполнить запрос при неинициализированном пуле соединений")
            raise RuntimeError("Пул соединений не инициализирован")
        
        query_type = query.strip().upper().split()[0] if query.strip() else "UNKNOWN"
        is_select = query_type == 'SELECT'
        
        async with self._lock:
            for attempt in range(max_retries):
                try:
                    async with self.pool.acquire() as conn:
                        # Если нужно принудительное обновление, отключаем кэш запросов
                        if force_refresh and is_select:
                            try:
                                async with conn.cursor(aiomysql.DictCursor) as temp_cur:
                                    await temp_cur.execute("SET SESSION query_cache_type = OFF")
                            except:
                                # Если не поддерживается, игнорируем
                                pass
                        async with conn.cursor(aiomysql.DictCursor) as cur:
                            # Логируем только важные операции (не SELECT)
                            if not is_select:
                                logging.warning(f"Выполнение {query_type} запроса (попытка {attempt + 1}/{max_retries})")
                            
                            await cur.execute(query, args or ())
                            
                            if is_select:
                                result = await cur.fetchall()
                                # SELECT запросы не логируем (слишком много)
                                return result
                            else:
                                await conn.commit()
                                lastrowid = cur.lastrowid
                                logging.warning(f"{query_type} запрос выполнен успешно, lastrowid: {lastrowid}")
                                return lastrowid
                except Exception as e:
                    if attempt == max_retries - 1:
                        logging.error(f"Ошибка выполнения запроса после {max_retries} попыток: {e}")
                        logging.error(f"Запрос: {query[:200]}...")  # Логируем первые 200 символов
                        raise e
                    logging.warning(f"Ошибка выполнения запроса (попытка {attempt + 1}/{max_retries}): {e}, повтор...")
                    await asyncio.sleep(0.1)
                    continue
    
    async def get_all_actors(self, force_refresh=False):
        return await self._select_all('actors', force_refresh=force_refresh)
    
    async def get_all_authors(self, force_refresh=False):
        return await self._select_all('authors', force_refresh=force_refresh)
    
    async def get_all_directors(self, force_refresh=False):
        return await self._select_all('directors', force_refresh=force_refresh)
    
    async def get_all_plays(self, force_refresh=False):
        return await self._select_all('plays', force_refresh=force_refresh)
    
    async def get_all_productions(self, force_refresh=False):
        return await self._select_all('productions', force_refresh=force_refresh)
    
    async def get_all_performances(self, force_refresh=False):
        return await self._select_all('performances', force_refresh=force_refresh)
    
    async def get_all_rehearsals(self, force_refresh=False):
        return await self._select_all('rehearsals', force_refresh=force_refresh)
    
    async def get_all_roles(self, force_refresh=False):
        return await self._select_all('roles', force_refresh=force_refresh)
    
    async def get_all_theatres(self, force_refresh=False):
        return await self._select_all('theatres', force_refresh=force_refresh)
    
    async def get_all_locations(self, force_refresh=False):
        return await self._select_all('locations', force_refresh=force_refresh)
    
    async def search_actors(self, search_text):
        return await self._search_records('actors', search_text)
    
    async def search_authors(self, search_text):
        return await self._search_records('authors', search_text)
    
    async def search_directors(self, search_text):
        return await self._search_records('directors', search_text)
    
    async def search_plays(self, search_text):
        return await self._search_records('plays', search_text)
    
    async def search_productions(self, search_text):
        return await self._search_records('productions', search_text)
    
    async def search_performances(self, search_text):
        return await self._search_records('performances', search_text)
    
    async def search_rehearsals(self, search_text):
        return await self._search_records('rehearsals', search_text)
    
    async def search_roles(self, search_text):
        return await self._search_records('roles', search_text)
    
    async def search_theatres(self, search_text):
        return await self._search_records('theatres', search_text, sort_column='name')
    
    async def search_locations(self, search_text):
        return await self._search_records('locations', search_text, sort_column='theatre_name')
    
    async def get_theatre_by_id(self, theatre_id):
        result = await self.execute_query("SELECT * FROM theatre WHERE id = %s", (theatre_id,))
        return result[0] if result else None
    
    async def get_location_by_id(self, location_id):
        result = await self.execute_query("""
            SELECT l.*, t.name as theatre_name, t.city, t.street, t.house_number, t.postal_code
            FROM location l
            JOIN theatre t ON l.theatre_id = t.id
            WHERE l.id = %s
        """, (location_id,))
        return result[0] if result else None
    
    async def get_actor_by_id(self, actor_id):
        result = await self.execute_query("SELECT * FROM actor WHERE id = %s", (actor_id,))
        return result[0] if result else None
    
    async def get_author_by_id(self, author_id):
        result = await self.execute_query("SELECT * FROM author WHERE id = %s", (author_id,))
        return result[0] if result else None
    
    async def get_director_by_id(self, director_id):
        result = await self.execute_query("SELECT * FROM director WHERE id = %s", (director_id,))
        return result[0] if result else None
    
    async def get_play_by_id(self, play_id):
        result = await self.execute_query("SELECT * FROM play WHERE id = %s", (play_id,))
        return result[0] if result else None
    
    async def get_production_by_id(self, production_id):
        result = await self.execute_query("SELECT * FROM production WHERE id = %s", (production_id,))
        return result[0] if result else None
    
    async def get_performance_by_id(self, performance_id):
        result = await self.execute_query("SELECT * FROM performance WHERE id = %s", (performance_id,))
        return result[0] if result else None
    
    async def get_rehearsal_by_id(self, rehearsal_id):
        result = await self.execute_query("SELECT * FROM rehearsal WHERE id = %s", (rehearsal_id,))
        return result[0] if result else None
    
    async def get_role_by_id(self, role_id):
        result = await self.execute_query("SELECT * FROM role WHERE id = %s", (role_id,))
        return result[0] if result else None
    
    async def get_actors_for_production(self, production_id):
        return await self.execute_query("""
            SELECT a.* FROM actor a 
            JOIN actor_production ap ON a.id = ap.actor_id 
            WHERE ap.production_id = %s
        """, (production_id,))
    
    async def get_plays_for_author(self, author_id):
        return await self.execute_query("""
            SELECT p.* FROM play p 
            JOIN author_play ap ON p.id = ap.play_id 
            WHERE ap.author_id = %s
        """, (author_id,))
    
    async def get_roles_for_play(self, play_id):
        return await self.execute_query("""
            SELECT id, title 
            FROM role 
            WHERE play_id = %s
            ORDER BY title
        """, (play_id,))
    
    async def get_cast_for_production(self, production_id):
        return await self.execute_query("""
            SELECT 
                a.id as actor_id, a.full_name as actor_name,
                r.id as role_id, r.title as role_name
            FROM actor_role ar
            JOIN actor a ON ar.actor_id = a.id
            JOIN role r ON ar.role_id = r.id
            WHERE ar.production_id = %s
            ORDER BY a.full_name
        """, (production_id,))
    
    async def get_authors_for_play(self, play_id):
        return await self.execute_query("""
            SELECT a.id, a.full_name 
            FROM author_play ap
            JOIN author a ON ap.author_id = a.id
            WHERE ap.play_id = %s
        """, (play_id,))
    
    async def get_actors_for_rehearsal(self, rehearsal_id):
        return await self.execute_query("""
            SELECT a.* FROM actor a 
            JOIN actor_rehearsal ar ON a.id = ar.actor_id 
            WHERE ar.rehearsal_id = %s
            ORDER BY a.full_name
        """, (rehearsal_id,))
    
    async def get_actor_roles(self, actor_id):
        return await self.execute_query("""
            SELECT 
                ar.actor_id, ar.role_id, ar.production_id,
                r.title as role_name, r.description as role_description,
                p.title as production_title, p.production_date,
                pl.title as play_title
            FROM actor_role ar
            JOIN role r ON ar.role_id = r.id
            JOIN production p ON ar.production_id = p.id
            JOIN play pl ON p.play_id = pl.id
            WHERE ar.actor_id = %s
            ORDER BY p.production_date DESC, r.title
        """, (actor_id,))
    
    async def get_actor_rehearsals(self, actor_id):
        return await self.execute_query("""
            SELECT 
                r.id as rehearsal_id, r.datetime, r.production_id,
                p.title as production_title,
                l.hall_name, l.capacity,
                t.name as theatre_name, t.city, t.street, t.house_number
            FROM actor_rehearsal ar
            JOIN rehearsal r ON ar.rehearsal_id = r.id
            JOIN production p ON r.production_id = p.id
            JOIN location l ON r.location_id = l.id
            JOIN theatre t ON l.theatre_id = t.id
            WHERE ar.actor_id = %s
            ORDER BY r.datetime DESC
        """, (actor_id,))
    
    async def get_actor_productions(self, actor_id):
        return await self.execute_query("""
            SELECT 
                p.id as production_id, p.title, p.production_date, p.description,
                pl.title as play_title, pl.genre,
                d.full_name as director_name
            FROM actor_production ap
            JOIN production p ON ap.production_id = p.id
            JOIN play pl ON p.play_id = pl.id
            JOIN director d ON p.director_id = d.id
            WHERE ap.actor_id = %s
            ORDER BY p.production_date DESC
        """, (actor_id,))
    
    async def add_actor_to_production(self, actor_id, production_id):
        return await self.execute_query("""
            INSERT IGNORE INTO actor_production (actor_id, production_id)
            VALUES (%s, %s)
        """, (actor_id, production_id))
    
    async def remove_actor_from_production(self, actor_id, production_id):
        return await self.execute_query("""
            DELETE FROM actor_production 
            WHERE actor_id = %s AND production_id = %s
        """, (actor_id, production_id))
    
    async def add_actor_role(self, actor_id, role_id, production_id):
        return await self.execute_query("""
            INSERT IGNORE INTO actor_role (actor_id, role_id, production_id)
            VALUES (%s, %s, %s)
        """, (actor_id, role_id, production_id))
    
    async def remove_actor_role(self, actor_id, role_id, production_id):
        return await self.execute_query("""
            DELETE FROM actor_role 
            WHERE actor_id = %s AND role_id = %s AND production_id = %s
        """, (actor_id, role_id, production_id))
    
    async def add_actor_to_rehearsal(self, actor_id, rehearsal_id):
        return await self.execute_query("""
            INSERT IGNORE INTO actor_rehearsal (actor_id, rehearsal_id)
            VALUES (%s, %s)
        """, (actor_id, rehearsal_id))
    
    async def remove_actor_from_rehearsal(self, actor_id, rehearsal_id):
        return await self.execute_query("""
            DELETE FROM actor_rehearsal 
            WHERE actor_id = %s AND rehearsal_id = %s
        """, (actor_id, rehearsal_id))
    
    async def set_rehearsal_actors(self, rehearsal_id, actor_ids):
        if not self.pool:
            raise RuntimeError("Пул соединений не инициализирован")
        async with self._lock:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        # 1. Удаляем старых актеров
                        await cur.execute("DELETE FROM actor_rehearsal WHERE rehearsal_id = %s", (rehearsal_id,))
                        # 2. Вставляем новых
                        if actor_ids:
                            insert_query = "INSERT INTO actor_rehearsal (actor_id, rehearsal_id) VALUES (%s, %s)"
                            tuples_to_insert = [(actor_id, rehearsal_id) for actor_id in actor_ids]
                            await cur.executemany(insert_query, tuples_to_insert)
                        await conn.commit()
                    except Exception as e:
                        await conn.rollback()
                        logging.error(f"Ошибка транзакции set_rehearsal_actors: {e}")
                        raise e

    async def set_play_authors(self, play_id, author_ids):
        # author_ids - это список [1, 2, 3]

        if not self.pool:
            raise RuntimeError("Пул соединений не инициализирован")

        async with self._lock:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()

                        # 1. Удаляем старых авторов
                        await cur.execute("DELETE FROM author_play WHERE play_id = %s", (play_id,))

                        # 2. Вставляем новых
                        if author_ids:
                            insert_query = "INSERT INTO author_play (author_id, play_id) VALUES (%s, %s)"
                            tuples_to_insert = [(author_id, play_id) for author_id in author_ids]
                            await cur.executemany(insert_query, tuples_to_insert)

                        await conn.commit()
                    except Exception as e:
                        await conn.rollback()
                        logging.error(f"Ошибка транзакции set_play_authors: {e}")
                        raise e
    
    async def set_author_plays(self, author_id, play_ids):

        if not self.pool:
            raise RuntimeError("Пул соединений не инициализирован")

        async with self._lock:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()

                        # 1. Удаляем старые пьесы
                        await cur.execute("DELETE FROM author_play WHERE author_id = %s", (author_id,))

                        # 2. Вставляем новые
                        if play_ids:
                            insert_query = "INSERT INTO author_play (author_id, play_id) VALUES (%s, %s)"
                            tuples_to_insert = [(author_id, play_id) for play_id in play_ids]
                            await cur.executemany(insert_query, tuples_to_insert)

                        await conn.commit()
                    except Exception as e:
                        await conn.rollback()
                        logging.error(f"Ошибка транзакции set_author_plays: {e}")
                        raise e

    async def set_production_cast(self, production_id, cast_data):
        if not self.pool:
            raise RuntimeError("Пул соединений не инициализирован")

        async with self._lock:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        
                        # 1. Удаляем старый состав для этой постановки
                        await cur.execute("DELETE FROM actor_role WHERE production_id = %s", (production_id,))
                        
                        # 2. Вставляем новый состав
                        if cast_data:
                            insert_query = "INSERT INTO actor_role (actor_id, role_id, production_id) VALUES (%s, %s, %s)"
                            # Преобразуем список словарей в список кортежей
                            tuples_to_insert = [
                                (item['actor_id'], item['role_id'], production_id) 
                                for item in cast_data
                            ]
                            await cur.executemany(insert_query, tuples_to_insert)
                        
                        await conn.commit()
                    except Exception as e:
                        await conn.rollback()
                        logging.error(f"Ошибка транзакции set_production_cast: {e}")
                        raise e
    
    async def add_actor(self, full_name, experience):
        is_valid, error_msg = validate_full_name(full_name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO actor (full_name, experience) VALUES (%s, %s)",
            (full_name.strip(), experience)
        )
    
    async def update_actor(self, actor_id, full_name, experience):
        is_valid, error_msg = validate_full_name(full_name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE actor SET full_name=%s, experience=%s WHERE id=%s",
            (full_name.strip(), experience, actor_id)
        )
    
    async def delete_actor(self, actor_id):
        return await self.execute_query("DELETE FROM actor WHERE id=%s", (actor_id,))
    
    async def add_author(self, full_name, biography):
        is_valid, error_msg = validate_full_name(full_name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO author (full_name, biography) VALUES (%s, %s)",
            (full_name.strip(), biography)
        )
    
    async def update_author(self, author_id, full_name, biography):
        is_valid, error_msg = validate_full_name(full_name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE author SET full_name=%s, biography=%s WHERE id=%s",
            (full_name.strip(), biography, author_id)
        )
    
    async def delete_author(self, author_id):
        return await self.execute_query("DELETE FROM author WHERE id=%s", (author_id,))
    
    async def add_director(self, full_name, biography):
        is_valid, error_msg = validate_full_name(full_name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO director (full_name, biography) VALUES (%s, %s)",
            (full_name.strip(), biography)
        )
    
    async def update_director(self, director_id, full_name, biography):
        is_valid, error_msg = validate_full_name(full_name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE director SET full_name=%s, biography=%s WHERE id=%s",
            (full_name.strip(), biography, director_id)
        )
    
    async def delete_director(self, director_id):
        return await self.execute_query("DELETE FROM director WHERE id=%s", (director_id,))
    
    async def add_play(self, title, genre, year_written, description):
        is_valid, error_msg = validate_title(title)
        if not is_valid:
            raise ValueError(error_msg)
        is_valid, error_msg = validate_year(year_written)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO play (title, genre, year_written, description) VALUES (%s, %s, %s, %s)",
            (title.strip(), genre, year_written, description)
        )
    
    async def update_play(self, play_id, title, genre, year_written, description):
        is_valid, error_msg = validate_title(title)
        if not is_valid:
            raise ValueError(error_msg)
        is_valid, error_msg = validate_year(year_written)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE play SET title=%s, genre=%s, year_written=%s, description=%s WHERE id=%s",
            (title.strip(), genre, year_written, description, play_id)
        )
    
    async def delete_play(self, play_id):
        return await self.execute_query("DELETE FROM play WHERE id=%s", (play_id,))
    
    async def add_production(self, title, production_date, description, play_id, director_id):
        is_valid, error_msg = validate_title(title)
        if not is_valid:
            raise ValueError(error_msg)
        if production_date:
            is_valid, error_msg = validate_date(production_date)
            if not is_valid:
                raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO production (title, production_date, description, play_id, director_id) VALUES (%s, %s, %s, %s, %s)",
            (title.strip(), production_date, description, play_id, director_id)
        )
    
    async def update_production(self, production_id, title, production_date, description, play_id, director_id):
        is_valid, error_msg = validate_title(title)
        if not is_valid:
            raise ValueError(error_msg)
        if production_date:
            is_valid, error_msg = validate_date(production_date)
            if not is_valid:
                raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE production SET title=%s, production_date=%s, description=%s, play_id=%s, director_id=%s WHERE id=%s",
            (title.strip(), production_date, description, play_id, director_id, production_id)
        )
    
    async def delete_production(self, production_id):
        return await self.execute_query("DELETE FROM production WHERE id=%s", (production_id,))
    
    async def add_performance(self, datetime, location_id, production_id):
        is_valid, error_msg = validate_datetime(datetime)
        if not is_valid:
            raise ValueError(error_msg)
        if not location_id:
            raise ValueError("Место проведения обязательно")
        return await self.execute_query(
            "INSERT INTO performance (datetime, location_id, production_id) VALUES (%s, %s, %s)",
            (datetime, location_id, production_id)
        )
    
    async def update_performance(self, performance_id, datetime, location_id, production_id):
        is_valid, error_msg = validate_datetime(datetime)
        if not is_valid:
            raise ValueError(error_msg)
        if not location_id:
            raise ValueError("Место проведения обязательно")
        return await self.execute_query(
            "UPDATE performance SET datetime=%s, location_id=%s, production_id=%s WHERE id=%s",
            (datetime, location_id, production_id, performance_id)
        )
    
    async def delete_performance(self, performance_id):
        return await self.execute_query("DELETE FROM performance WHERE id=%s", (performance_id,))
    
    async def add_rehearsal(self, datetime, location_id, production_id):
        is_valid, error_msg = validate_datetime(datetime)
        if not is_valid:
            raise ValueError(error_msg)
        if not location_id:
            raise ValueError("Место проведения обязательно")
        return await self.execute_query(
            "INSERT INTO rehearsal (datetime, location_id, production_id) VALUES (%s, %s, %s)",
            (datetime, location_id, production_id)
        )
    
    async def update_rehearsal(self, rehearsal_id, datetime, location_id, production_id):
        is_valid, error_msg = validate_datetime(datetime)
        if not is_valid:
            raise ValueError(error_msg)
        if not location_id:
            raise ValueError("Место проведения обязательно")
        return await self.execute_query(
            "UPDATE rehearsal SET datetime=%s, location_id=%s, production_id=%s WHERE id=%s",
            (datetime, location_id, production_id, rehearsal_id)
        )
    
    async def delete_rehearsal(self, rehearsal_id):
        return await self.execute_query("DELETE FROM rehearsal WHERE id=%s", (rehearsal_id,))
    
    async def add_role(self, title, description, play_id):
        is_valid, error_msg = validate_title(title)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO role (title, description, play_id) VALUES (%s, %s, %s)",
            (title.strip(), description, play_id)
        )
    
    async def update_role(self, role_id, title, description, play_id):
        is_valid, error_msg = validate_title(title)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE role SET title=%s, description=%s, play_id=%s WHERE id=%s",
            (title.strip(), description, play_id, role_id)
        )
    
    async def add_theatre(self, name, city=None, street=None, house_number=None, postal_code=None):
        is_valid, error_msg = validate_title(name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO theatre (name, city, street, house_number, postal_code) VALUES (%s, %s, %s, %s, %s)",
            (name.strip(), city.strip() if city else None, street.strip() if street else None, 
             house_number.strip() if house_number else None, postal_code.strip() if postal_code else None)
        )
    
    async def update_theatre(self, theatre_id, name, city=None, street=None, house_number=None, postal_code=None):
        is_valid, error_msg = validate_title(name)
        if not is_valid:
            raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE theatre SET name=%s, city=%s, street=%s, house_number=%s, postal_code=%s WHERE id=%s",
            (name.strip(), city.strip() if city else None, street.strip() if street else None,
             house_number.strip() if house_number else None, postal_code.strip() if postal_code else None, theatre_id)
        )
    
    async def delete_theatre(self, theatre_id):
        return await self.execute_query("DELETE FROM theatre WHERE id=%s", (theatre_id,))
    
    async def add_location(self, theatre_id, hall_name, capacity=None):
        if not theatre_id:
            raise ValueError("Необходимо указать театр")
        is_valid, error_msg = validate_title(hall_name)
        if not is_valid:
            raise ValueError(error_msg)
        if capacity is not None:
            is_valid, error_msg = validate_capacity(capacity)
            if not is_valid:
                raise ValueError(error_msg)
        return await self.execute_query(
            "INSERT INTO location (theatre_id, hall_name, capacity) VALUES (%s, %s, %s)",
            (theatre_id, hall_name.strip(), capacity)
        )
    
    async def update_location(self, location_id, theatre_id, hall_name, capacity=None):
        if not theatre_id:
            raise ValueError("Необходимо указать театр")
        is_valid, error_msg = validate_title(hall_name)
        if not is_valid:
            raise ValueError(error_msg)
        if capacity is not None:
            is_valid, error_msg = validate_capacity(capacity)
            if not is_valid:
                raise ValueError(error_msg)
        return await self.execute_query(
            "UPDATE location SET theatre_id=%s, hall_name=%s, capacity=%s WHERE id=%s",
            (theatre_id, hall_name.strip(), capacity, location_id)
        )
    
    async def delete_location(self, location_id):
        return await self.execute_query("DELETE FROM location WHERE id=%s", (location_id,))
    
    async def delete_role(self, role_id):
        return await self.execute_query("DELETE FROM role WHERE id=%s", (role_id,))
    
    async def get_rehearsals_by_month(self, filters=None):
        try:
            # Базовый запрос
            where_conditions = []
            joins = []
            params = []
            
            if filters:
                # Фильтр по периоду
                period = filters.get('period', 'весь')
                if period == 'неделя':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 WEEK)")
                elif period == 'месяц':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 MONTH)")
                elif period == 'квартал':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 3 MONTH)")
                elif period == 'год':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 YEAR)")
                # 'весь' - без ограничения по дате
                
                # Фильтр по режиссеру
                if filters.get('director') and filters['director'] != 'все':
                    joins.append("JOIN production pr ON r.production_id = pr.id")
                    joins.append("JOIN director d ON pr.director_id = d.id")
                    where_conditions.append("d.full_name = %s")
                    params.append(filters['director'])
                
                # Фильтр по театру
                if filters.get('theatre') and filters['theatre'] != 'все':
                    if "JOIN location loc" not in " ".join(joins):
                        joins.append("JOIN location loc ON r.location_id = loc.id")
                    if "JOIN theatre t" not in " ".join(joins):
                        joins.append("JOIN theatre t ON loc.theatre_id = t.id")
                    where_conditions.append("t.name = %s")
                    params.append(filters['theatre'])
            
            # Если нет условий по дате, ограничиваем последним годом для производительности
            if not any('datetime' in cond for cond in where_conditions):
                where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 YEAR)")
            
            join_clause = " ".join(joins) if joins else ""
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            query = f"""
                SELECT DATE_FORMAT(r.datetime, '%%Y-%%m') as month, COUNT(*) as count 
                FROM rehearsal r
                {join_clause}
                WHERE {where_clause}
                GROUP BY month 
                ORDER BY month
            """
            
            result = await self.execute_query(query, tuple(params) if params else None)
            return result if result else []
        except Exception as e:
            logging.error(f"Ошибка получения репетиций по месяцам: {e}")
            return []
    
    async def get_plays_by_genre(self):
        try:
            result = await self.execute_query("""
                SELECT genre, COUNT(*) as count 
                FROM play 
                WHERE genre IS NOT NULL AND genre != ''
                GROUP BY genre
                ORDER BY count DESC
            """)
            return result if result else []
        except Exception as e:
            logging.error(f"Ошибка получения пьес по жанрам: {e}")
            return []
    
    async def get_upcoming_rehearsals(self, limit=10, filters=None):
        try:
            where_conditions = []
            params = []
            
            if filters:
                # Фильтр по периоду
                period = filters.get('period', 'весь')
                if period == 'неделя':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 WEEK)")
                elif period == 'месяц':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 MONTH)")
                elif period == 'квартал':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 3 MONTH)")
                elif period == 'год':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 YEAR)")
                # 'весь' - без ограничения по дате, но показываем только будущие
                if period == 'весь':
                    where_conditions.append("r.datetime >= NOW()")
                else:
                    where_conditions.append("r.datetime >= NOW()")
                
                # Фильтр по режиссеру
                if filters.get('director') and filters['director'] != 'все':
                    where_conditions.append("d.full_name = %s")
                    params.append(filters['director'])
                
                # Фильтр по театру
                if filters.get('theatre') and filters['theatre'] != 'все':
                    where_conditions.append("t.name = %s")
                    params.append(filters['theatre'])
            else:
                # По умолчанию показываем только будущие репетиции
                where_conditions.append("r.datetime >= NOW()")
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "r.datetime >= NOW()"
            
            query = f"""
                SELECT r.*, pr.title as production_title, d.full_name as director_name, 
                       pl.title as play_title, pl.genre, t.name as theatre_name, l.hall_name as location_name
                FROM rehearsal r
                JOIN production pr ON r.production_id = pr.id
                JOIN play pl ON pr.play_id = pl.id
                JOIN director d ON pr.director_id = d.id
                JOIN location l ON r.location_id = l.id
                JOIN theatre t ON l.theatre_id = t.id
                WHERE {where_clause}
                ORDER BY r.datetime ASC
                LIMIT {limit}
            """
            
            result = await self.execute_query(query, tuple(params) if params else None)
            return result if result else []
        except Exception as e:
            logging.error(f"Ошибка получения предстоящих репетиций: {e}")
            return []
    
    async def get_filtered_rehearsals_count(self, filters=None):
        try:
            where_conditions = []
            joins = []
            params = []
            
            if filters:
                period = filters.get('period', 'весь')
                if period == 'неделя':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 WEEK)")
                elif period == 'месяц':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 MONTH)")
                elif period == 'квартал':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 3 MONTH)")
                elif period == 'год':
                    where_conditions.append("r.datetime >= DATE_SUB(NOW(), INTERVAL 1 YEAR)")
                # 'весь' - без ограничения по дате
                
                if filters.get('director') and filters['director'] != 'все':
                    joins.append("JOIN production pr ON r.production_id = pr.id")
                    joins.append("JOIN director d ON pr.director_id = d.id")
                    where_conditions.append("d.full_name = %s")
                    params.append(filters['director'])
                
                if filters.get('theatre') and filters['theatre'] != 'все':
                    if "JOIN location loc" not in " ".join(joins):
                        joins.append("JOIN location loc ON r.location_id = loc.id")
                    if "JOIN theatre t" not in " ".join(joins):
                        joins.append("JOIN theatre t ON loc.theatre_id = t.id")
                    where_conditions.append("t.name = %s")
                    params.append(filters['theatre'])
            
            join_clause = " ".join(joins) if joins else ""
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            query = f"""
                SELECT COUNT(*) as count 
                FROM rehearsal r
                {join_clause}
                WHERE {where_clause}
            """
            
            result = await self.execute_query(query, tuple(params) if params else None)
            return result[0]['count'] if result and len(result) > 0 else 0
        except Exception as e:
            logging.error(f"Ошибка получения количества репетиций: {e}")
            return 0
    
    async def get_actors_count_by_production(self, production_id):
        try:
            result = await self.execute_query("""
                SELECT COUNT(*) as count 
                FROM actor_production 
                WHERE production_id = %s
            """, (production_id,))
            return result[0]['count'] if result and len(result) > 0 else 0
        except Exception as e:
            logging.error(f"Ошибка получения количества актеров: {e}")
            return 0
    
    async def get_total_roles(self):
        try:
            result = await self.execute_query("SELECT COUNT(*) as count FROM role")
            return result[0]['count'] if result and len(result) > 0 else 0
        except Exception as e:
            logging.error(f"Ошибка получения количества ролей: {e}")
            return 0
    
    async def get_unique_genres(self):
        return await self._get_unique_values('play', 'genre')
    
    async def get_unique_actor_names(self):
        return await self._get_unique_values('actor', 'full_name')
    
    async def get_unique_author_names(self):
        return await self._get_unique_values('author', 'full_name')
    
    async def get_unique_director_names(self):
        return await self._get_unique_values('director', 'full_name')
    
    async def get_unique_play_titles(self):
        return await self._get_unique_values('play', 'title')
    
    async def get_unique_theatres(self):
        return await self._get_unique_values('theatre', 'name')
    
    async def get_unique_locations(self):
        return await self._get_unique_values('location', 'hall_name')
    
    async def get_unique_production_titles(self):
        return await self._get_unique_values('production', 'title')
    
    async def get_unique_role_titles(self):
        return await self._get_unique_values('role', 'title')
    
    async def get_all_actors_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('actors', sort_column, sort_ascending, force_refresh)
    
    async def get_all_authors_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('authors', sort_column, sort_ascending, force_refresh)
    
    async def get_all_directors_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('directors', sort_column, sort_ascending, force_refresh)
    
    async def get_all_plays_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('plays', sort_column, sort_ascending, force_refresh)
    
    async def get_all_productions_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('productions', sort_column, sort_ascending, force_refresh)
    
    async def get_all_performances_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('performances', sort_column, sort_ascending, force_refresh)
    
    async def get_all_rehearsals_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('rehearsals', sort_column, sort_ascending, force_refresh)
    
    async def get_all_roles_sorted(self, sort_column='id', sort_ascending=True, force_refresh=False):
        return await self._select_all('roles', sort_column, sort_ascending, force_refresh)
    
    async def get_all_theatres_sorted(self, sort_column='name', sort_ascending=True, force_refresh=False):
        return await self._select_all('theatres', sort_column, sort_ascending, force_refresh)
    
    async def get_all_locations_sorted(self, sort_column='hall_name', sort_ascending=True, force_refresh=False):
        return await self._select_all('locations', sort_column, sort_ascending, force_refresh)
    
    async def search_actors_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('actors', search_text, sort_column, sort_ascending)
    
    async def search_authors_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('authors', search_text, sort_column, sort_ascending)
    
    async def search_directors_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('directors', search_text, sort_column, sort_ascending)
    
    async def search_plays_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('plays', search_text, sort_column, sort_ascending)
    
    async def search_productions_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('productions', search_text, sort_column, sort_ascending)
    
    async def search_performances_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('performances', search_text, sort_column, sort_ascending)
    
    async def search_rehearsals_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('rehearsals', search_text, sort_column, sort_ascending)
    
    async def search_roles_sorted(self, search_text, sort_column='id', sort_ascending=True):
        return await self._search_records('roles', search_text, sort_column, sort_ascending)
    
    async def search_theatres_sorted(self, search_text, sort_column='name', sort_ascending=True):
        return await self._search_records('theatres', search_text, sort_column, sort_ascending)
    
    async def search_locations_sorted(self, search_text, sort_column='hall_name', sort_ascending=True):
        return await self._search_records('locations', search_text, sort_column, sort_ascending)

