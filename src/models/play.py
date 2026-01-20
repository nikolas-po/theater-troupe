"""
Модель пьесы.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Play:
    """Модель пьесы"""
    id: Optional[int] = None
    title: str = ""
    genre: str = ""
    year_written: Optional[int] = None
    description: str = ""
    
    def __str__(self):
        year_str = f" ({self.year_written})" if self.year_written else ""
        return f"{self.title}{year_str}"
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'title': self.title,
            'genre': self.genre,
            'year_written': self.year_written,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        return cls(
            id=data.get('id'),
            title=data.get('title', ''),
            genre=data.get('genre', ''),
            year_written=data.get('year_written'),
            description=data.get('description', '')
        )

