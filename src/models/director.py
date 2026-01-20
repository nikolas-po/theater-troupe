"""
Модель режиссера.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Director:
    """Модель режиссера"""
    id: Optional[int] = None
    full_name: str = ""
    biography: str = ""
    
    def __str__(self):
        return self.full_name
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'full_name': self.full_name,
            'biography': self.biography
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        return cls(
            id=data.get('id'),
            full_name=data.get('full_name', ''),
            biography=data.get('biography', '')
        )

