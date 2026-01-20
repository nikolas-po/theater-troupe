"""
Модель спектакля.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime as dt


@dataclass
class Performance:
    """Модель спектакля"""
    id: Optional[int] = None
    datetime: Optional[dt] = None
    location_id: Optional[int] = None
    production_id: Optional[int] = None
    
    def __str__(self):
        dt_str = self.datetime.strftime('%d.%m.%Y %H:%M') if self.datetime else "Дата не указана"
        return f"Спектакль {dt_str}"
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'datetime': self.datetime.isoformat() if self.datetime else None,
            'location_id': self.location_id,
            'production_id': self.production_id
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        dt_val = data.get('datetime')
        if isinstance(dt_val, str):
            try:
                dt_val = dt.fromisoformat(dt_val.replace(' ', 'T'))
            except:
                dt_val = None
        
        return cls(
            id=data.get('id'),
            datetime=dt_val,
            location_id=data.get('location_id'),
            production_id=data.get('production_id')
        )

