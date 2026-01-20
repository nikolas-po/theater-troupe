"""
Модель актера.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Actor:
    """Модель актера театральной труппы"""
    id: Optional[int] = None
    full_name: str = ""
    experience: int = 0
    
    def __str__(self):
        return f"{self.full_name} (опыт: {self.experience} лет)"
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'full_name': self.full_name,
            'experience': self.experience
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        return cls(
            id=data.get('id'),
            full_name=data.get('full_name', ''),
            experience=data.get('experience', 0)
        )

