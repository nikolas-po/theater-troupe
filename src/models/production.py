"""
Модель постановки.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import date


@dataclass
class Production:
    """Модель постановки"""
    id: Optional[int] = None
    title: str = ""
    production_date: Optional[date] = None
    description: str = ""
    play_id: Optional[int] = None
    director_id: Optional[int] = None
    
    def __str__(self):
        return self.title
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'title': self.title,
            'production_date': self.production_date.isoformat() if self.production_date else None,
            'description': self.description,
            'play_id': self.play_id,
            'director_id': self.director_id
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        prod_date = data.get('production_date')
        if isinstance(prod_date, str):
            from datetime import datetime
            try:
                prod_date = datetime.strptime(prod_date, '%Y-%m-%d').date()
            except:
                prod_date = None
        
        return cls(
            id=data.get('id'),
            title=data.get('title', ''),
            production_date=prod_date,
            description=data.get('description', ''),
            play_id=data.get('play_id'),
            director_id=data.get('director_id')
        )

