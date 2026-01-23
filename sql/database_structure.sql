-- phpMyAdmin SQL Dump
-- version 5.2.2deb1+deb13u1
-- https://www.phpmyadmin.net/
--
-- Хост: localhost:3306
-- Время создания: Янв 23 2026 г., 12:56
-- Версия сервера: 11.8.3-MariaDB-0+deb13u1 from Debian
-- Версия PHP: 8.4.16

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- База данных: `nik`
--

-- --------------------------------------------------------

--
-- Структура таблицы `actor`
--

CREATE TABLE `actor` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор актера',
  `full_name` varchar(255) NOT NULL COMMENT 'Полное имя актера',
  `experience` text DEFAULT NULL COMMENT 'Опыт и портфолио актера',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица актеров';

-- --------------------------------------------------------

--
-- Структура таблицы `actor_production`
--

CREATE TABLE `actor_production` (
  `actor_id` bigint(20) NOT NULL COMMENT 'Идентификатор актера',
  `production_id` bigint(20) NOT NULL COMMENT 'Идентификатор постановки',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания связи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления связи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица связи актеров и постановок';

-- --------------------------------------------------------

--
-- Структура таблицы `actor_rehearsal`
--

CREATE TABLE `actor_rehearsal` (
  `actor_id` bigint(20) NOT NULL COMMENT 'Идентификатор актера',
  `rehearsal_id` bigint(20) NOT NULL COMMENT 'Идентификатор репетиции',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания связи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления связи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица связи актеров и репетиций';

-- --------------------------------------------------------

--
-- Структура таблицы `actor_role`
--

CREATE TABLE `actor_role` (
  `actor_id` bigint(20) NOT NULL COMMENT 'Идентификатор актера',
  `role_id` bigint(20) NOT NULL COMMENT 'Идентификатор роли',
  `production_id` bigint(20) NOT NULL COMMENT 'Идентификатор постановки',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания связи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления связи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица связи актеров, ролей и постановок';

-- --------------------------------------------------------

--
-- Структура таблицы `author`
--

CREATE TABLE `author` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор автора',
  `full_name` varchar(255) NOT NULL COMMENT 'Полное имя автора',
  `biography` text DEFAULT NULL COMMENT 'Биография автора',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица авторов пьес';

-- --------------------------------------------------------

--
-- Структура таблицы `author_play`
--

CREATE TABLE `author_play` (
  `author_id` bigint(20) NOT NULL COMMENT 'Идентификатор автора',
  `play_id` bigint(20) NOT NULL COMMENT 'Идентификатор пьесы',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания связи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления связи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица связи авторов и пьес';

-- --------------------------------------------------------

--
-- Структура таблицы `director`
--

CREATE TABLE `director` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор режиссера',
  `full_name` varchar(255) NOT NULL COMMENT 'Полное имя режиссера',
  `biography` text DEFAULT NULL COMMENT 'Биография режиссера',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица режиссеров';

-- --------------------------------------------------------

--
-- Структура таблицы `location`
--

CREATE TABLE `location` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор места',
  `theatre_id` bigint(20) NOT NULL COMMENT 'Идентификатор театра',
  `hall_name` varchar(255) NOT NULL COMMENT 'Название зала/сцены',
  `capacity` int(11) DEFAULT NULL COMMENT 'Вместимость (количество мест)',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица залов/сцен театров';

-- --------------------------------------------------------

--
-- Структура таблицы `performance`
--

CREATE TABLE `performance` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор спектакля',
  `datetime` timestamp NOT NULL COMMENT 'Дата и время проведения спектакля',
  `location_id` bigint(20) NOT NULL COMMENT 'Идентификатор места проведения',
  `production_id` bigint(20) NOT NULL COMMENT 'Идентификатор постановки',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица спектаклей';

-- --------------------------------------------------------

--
-- Структура таблицы `play`
--

CREATE TABLE `play` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор пьесы',
  `title` varchar(255) NOT NULL COMMENT 'Название пьесы',
  `genre` varchar(100) DEFAULT NULL COMMENT 'Жанр пьесы',
  `year_written` int(11) DEFAULT NULL COMMENT 'Год написания пьесы',
  `description` text DEFAULT NULL COMMENT 'Описание пьесы',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица пьес';

-- --------------------------------------------------------

--
-- Структура таблицы `production`
--

CREATE TABLE `production` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор постановки',
  `title` varchar(255) NOT NULL COMMENT 'Название постановки',
  `production_date` date DEFAULT NULL COMMENT 'Дата постановки',
  `description` text DEFAULT NULL COMMENT 'Описание постановки',
  `play_id` bigint(20) NOT NULL COMMENT 'Идентификатор пьесы',
  `director_id` bigint(20) NOT NULL COMMENT 'Идентификатор режиссера',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица постановок пьес';

-- --------------------------------------------------------

--
-- Структура таблицы `rehearsal`
--

CREATE TABLE `rehearsal` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор репетиции',
  `datetime` timestamp NOT NULL COMMENT 'Дата и время проведения репетиции',
  `location_id` bigint(20) NOT NULL COMMENT 'Идентификатор места проведения',
  `production_id` bigint(20) NOT NULL COMMENT 'Идентификатор постановки',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица репетиций';

-- --------------------------------------------------------

--
-- Структура таблицы `role`
--

CREATE TABLE `role` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор роли',
  `title` varchar(255) NOT NULL COMMENT 'Название роли',
  `description` text DEFAULT NULL COMMENT 'Описание роли',
  `play_id` bigint(20) NOT NULL COMMENT 'Идентификатор пьесы',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица ролей в пьесах';

-- --------------------------------------------------------

--
-- Структура таблицы `theatre`
--

CREATE TABLE `theatre` (
  `id` bigint(20) NOT NULL COMMENT 'Уникальный идентификатор театра',
  `name` varchar(255) NOT NULL COMMENT 'Название театра',
  `city` varchar(100) DEFAULT NULL COMMENT 'Город',
  `street` varchar(200) DEFAULT NULL COMMENT 'Улица',
  `house_number` varchar(20) DEFAULT NULL COMMENT 'Номер дома',
  `postal_code` varchar(20) DEFAULT NULL COMMENT 'Почтовый индекс',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата и время создания записи',
  `updated_at` timestamp NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Дата и время последнего обновления записи'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Таблица театров';

--
-- Индексы сохранённых таблиц
--

--
-- Индексы таблицы `actor`
--
ALTER TABLE `actor`
  ADD PRIMARY KEY (`id`);

--
-- Индексы таблицы `actor_production`
--
ALTER TABLE `actor_production`
  ADD PRIMARY KEY (`actor_id`,`production_id`),
  ADD KEY `idx_actor_production_production` (`production_id`);

--
-- Индексы таблицы `actor_rehearsal`
--
ALTER TABLE `actor_rehearsal`
  ADD PRIMARY KEY (`actor_id`,`rehearsal_id`),
  ADD KEY `idx_actor_rehearsal_rehearsal` (`rehearsal_id`);

--
-- Индексы таблицы `actor_role`
--
ALTER TABLE `actor_role`
  ADD PRIMARY KEY (`actor_id`,`role_id`,`production_id`),
  ADD KEY `idx_actor_role_role` (`role_id`),
  ADD KEY `idx_actor_role_production` (`production_id`);

--
-- Индексы таблицы `author`
--
ALTER TABLE `author`
  ADD PRIMARY KEY (`id`);

--
-- Индексы таблицы `author_play`
--
ALTER TABLE `author_play`
  ADD PRIMARY KEY (`author_id`,`play_id`),
  ADD KEY `idx_author_play_play` (`play_id`);

--
-- Индексы таблицы `director`
--
ALTER TABLE `director`
  ADD PRIMARY KEY (`id`);

--
-- Индексы таблицы `location`
--
ALTER TABLE `location`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_location_theatre_hall` (`theatre_id`,`hall_name`);

--
-- Индексы таблицы `performance`
--
ALTER TABLE `performance`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_performance_location` (`location_id`),
  ADD KEY `idx_performance_production` (`production_id`);

--
-- Индексы таблицы `play`
--
ALTER TABLE `play`
  ADD PRIMARY KEY (`id`);

--
-- Индексы таблицы `production`
--
ALTER TABLE `production`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_production_play` (`play_id`),
  ADD KEY `idx_production_director` (`director_id`);

--
-- Индексы таблицы `rehearsal`
--
ALTER TABLE `rehearsal`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_rehearsal_location` (`location_id`),
  ADD KEY `idx_rehearsal_production` (`production_id`);

--
-- Индексы таблицы `role`
--
ALTER TABLE `role`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_role_play` (`play_id`);

--
-- Индексы таблицы `theatre`
--
ALTER TABLE `theatre`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_theatre_name` (`name`);

--
-- AUTO_INCREMENT для сохранённых таблиц
--

--
-- AUTO_INCREMENT для таблицы `actor`
--
ALTER TABLE `actor`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор актера';

--
-- AUTO_INCREMENT для таблицы `author`
--
ALTER TABLE `author`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор автора';

--
-- AUTO_INCREMENT для таблицы `director`
--
ALTER TABLE `director`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор режиссера';

--
-- AUTO_INCREMENT для таблицы `location`
--
ALTER TABLE `location`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор места';

--
-- AUTO_INCREMENT для таблицы `performance`
--
ALTER TABLE `performance`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор спектакля';

--
-- AUTO_INCREMENT для таблицы `play`
--
ALTER TABLE `play`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор пьесы';

--
-- AUTO_INCREMENT для таблицы `production`
--
ALTER TABLE `production`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор постановки';

--
-- AUTO_INCREMENT для таблицы `rehearsal`
--
ALTER TABLE `rehearsal`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор репетиции';

--
-- AUTO_INCREMENT для таблицы `role`
--
ALTER TABLE `role`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор роли';

--
-- AUTO_INCREMENT для таблицы `theatre`
--
ALTER TABLE `theatre`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Уникальный идентификатор театра';
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
