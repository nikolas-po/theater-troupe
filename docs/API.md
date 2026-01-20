# API Документация

## Модуль экспорта отчетов

### `src.utils.export_manager.ExportManager`

Менеджер для управления экспортом отчетов с поддержкой выбора формата и пути сохранения.

#### Методы:

- `export_statistical_report(parent, format_type, filepath)` - Экспорт статистического отчета
- `export_detailed_report(parent, format_type, filepath)` - Экспорт детального отчета  
- `export_excel_report(parent, format_type, filepath)` - Экспорт полного Excel отчета
- `show_export_dialog(parent, report_name, formats)` - Показывает диалог выбора формата и пути

### `src.api.reports.ReportExportDialog`

Диалог выбора формата и пути сохранения отчета.

#### Параметры:
- `parent` - Родительское окно
- `report_name` - Название отчета
- `default_formats` - Список доступных форматов (по умолчанию ['PDF', 'XLSX'])

## Модели данных

Все модели находятся в `src.models` и поддерживают методы:
- `to_dict()` - Преобразование в словарь
- `from_dict(data)` - Создание из словаря

### Доступные модели:
- `Actor` - Актер
- `Author` - Автор
- `Director` - Режиссер
- `Play` - Пьеса
- `Production` - Постановка
- `Performance` - Спектакль
- `Rehearsal` - Репетиция
- `Role` - Роль
- `Theatre` - Театр
- `Location` - Место проведения

