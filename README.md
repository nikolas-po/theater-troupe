# Театральная система управления

Система управления театральной труппой с графическим интерфейсом на Python для управления всеми аспектами театральной деятельности.

## Оглавление

- [Особенности](#особенности)
- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Использование](#использование)
- [Структура базы данных](#структура-базы-данных)
- [Структура проекта](#структура-проекта)

## Особенности

- **Полный цикл управления театром**: актеры, режиссеры, пьесы, постановки, спектакли, репетиции
- **Графический пользовательский интерфейс**: интуитивно понятное управление
- **Поддержка MySQL**: надежное хранение данных
- **Экспорт отчетов**: генерация PDF и Excel отчетов
- **Поиск и фильтрация**: быстрый доступ к информации

## Требования

### Системные требования

- **ОС**: Windows 10/11, Linux (Ubuntu 20.04+, Debian 10+), macOS 10.15+
- **Python**: 3.8 или выше
- **MySQL**: 8.0 или выше (или MariaDB 10.6+)

### Зависимости Python

Смотрите `requirements.txt` для полного списка зависимостей.

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/nikolas-po/theater-troupe.git
cd theater-troupe
```
### 2. Создание виртуального окружения
```bash

# Для Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Для Windows
python -m venv venv
venv\Scripts\activate
```
### 3. Установка зависимостей
```bash

pip install --upgrade pip
pip install -r requirements.txt
```
### 4. Настройка MySQL
**Установка MySQL (если не установлен):**
```bash

# Для Debian/Ubuntu
sudo apt update
sudo apt install mysql-server mysql-client -y
sudo systemctl start mysql
sudo systemctl enable mysql

# Для Windows
# Скачайте установщик с официального сайта MySQL
```
**Создание базы данных и пользователя:**
```sql

-- Подключитесь к MySQL как root
mysql -u root -p

-- Создайте базу данных 
CREATE DATABASE bd CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Создайте пользователя
CREATE USER 'theater_user'@'localhost' IDENTIFIED BY 'ваш_пароль';

-- Предоставьте права
GRANT ALL PRIVILEGES ON bd.* TO 'theater_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 5. Настройка переменных окружения
```bash

# Скопируйте шаблон
cp .env.example .env

# Отредактируйте файл .env
nano .env  # или используйте любой текстовый редактор

Содержимое .env файла:
env

# Настройки MySQL
DB_HOST=localhost
DB_PORT=3306
DB_NAME=user           # Имя базы данных из дампа
DB_USER=theater_user   # Пользователь, созданный выше
DB_PASSWORD=ваш_пароль # Пароль, указанный при создании пользователя
```
### 6. Запуск приложения
```bash

python src/main.py
```
**Конфигурация**
**Файл .env**
```env

DB_HOST=localhost
DB_PORT=3306
DB_NAME=user
DB_USER=theater_user
DB_PASSWORD=your_password
DB_CHARSET=utf8mb4
```
**Конфигурационный файл базы данных**
```python

# config/database.py
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'charset': os.getenv('DB_CHARSET')
}
```
## Использование
**Запуск приложения**
```bash

python src/main.py
```
### Основные функции интерфейса:

**Управление актерами**

- Добавление новых актеров

- Редактирование информации об опыте

- Просмотр участия в постановках

**Управление постановками**

- Создание новых постановок

- Назначение режиссеров и актеров

- Планирование репетиций и спектаклей

**Расписание**

- Просмотр расписания спектаклей

- Управление репетициями

- Назначение мест проведения

**Отчеты**

- Экспорт в PDF и Excel

### Экспорт данных
Приложение поддерживает экспорт отчетов в форматах PDF и XLSX через графический интерфейс.

Отчеты сохраняются в папку `reports/` по умолчанию, но можно выбрать любое место сохранения через диалог экспорта.

Подробнее см. [docs/EXPORT.md](docs/EXPORT.md)

## Структура базы данных

База данных включает следующие таблицы:

**Основные таблицы:**

- actor - Актеры театра

- author - Авторы пьес

- director - Режиссеры

- play - Пьесы

- production - Постановки

- performance - Спектакли

- rehearsal - Репетиции

- role - Роли в пьесах

- theatre - Театры

- location - Места проведения (залы, сцены)

**Таблицы связей:**

- actor_production - Связь актеров и постановок

- actor_rehearsal - Связь актеров и репетиций

- actor_role - Связь актеров и ролей

- author_play - Связь авторов и пьес

## Структура проекта
```text

theater-troupe/
├── venv/              # Виртуальное окружение
├── src/               # Исходный код
│   ├── __init__.py
│   ├── main.py        # Главный модуль с UI
│   ├── models/        # Модели данных
│   ├── database/      # Работа с БД
│   │   ├── __init__.py
│   │   ├── connection.py  # Подключение к MySQL
│   │   └── queries.py     # SQL запросы
│   ├── api/           # API endpoints
│   ├── utils/         # Вспомогательные функции
│   │   ├── __init__.py
│   │   ├── theme.py       # Управление темами
│   │   └── validators.py  # Валидация данных
│   ├── export_to_pdf.py   # Экспорт в PDF
│   └── export_to_xlsx.py  # Экспорт в Excel
├── config/            # Конфигурация
│   ├── __init__.py
│   └── database.py    # Конфигурация БД
├── docs/              # Документация
│   ├── API.md         # API документация
│   └── EXPORT.md      # Руководство по экспорту
├── reports/                   # Экспортированные отчеты
├── requirements.txt           # Основные зависимости
├── requirements-dev.txt       # Зависимости для разработки
├── theatre_system.log         # Логи системы
├── .env.example               # Шаблон переменных окружения
├── .gitignore                 # Игнорируемые файлы
└── README.md                  # Документация
```












