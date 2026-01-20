"""
Модель места проведения.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Location:
    """Модель места проведения (зал в театре)"""
    id: Optional[int] = None
    theatre_id: Optional[int] = None
    hall_name: str = ""
    capacity: Optional[int] = None
    
    def __str__(self):
        return self.hall_name
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'theatre_id': self.theatre_id,
            'hall_name': self.hall_name,
            'capacity': self.capacity
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        return cls(
            id=data.get('id'),
            theatre_id=data.get('theatre_id'),
            hall_name=data.get('hall_name', ''),
            capacity=data.get('capacity')
        )

