"""
Модель роли.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Role:
    """Модель роли в пьесе"""
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    play_id: Optional[int] = None
    
    def __str__(self):
        return self.title
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'play_id': self.play_id
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        return cls(
            id=data.get('id'),
            title=data.get('title', ''),
            description=data.get('description', ''),
            play_id=data.get('play_id')
        )

