"""
Модель театра.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Theatre:
    """Модель театра"""
    id: Optional[int] = None
    name: str = ""
    city: Optional[str] = None
    street: Optional[str] = None
    house_number: Optional[str] = None
    postal_code: Optional[str] = None
    
    def __str__(self):
        return self.name
    
    def get_full_address(self) -> str:
        """Возвращает полный адрес театра"""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.street:
            street_part = self.street
            if self.house_number:
                street_part += f", {self.house_number}"
            parts.append(street_part)
        if self.postal_code:
            parts.append(self.postal_code)
        return ", ".join(parts) if parts else "Адрес не указан"
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'city': self.city,
            'street': self.street,
            'house_number': self.house_number,
            'postal_code': self.postal_code
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект из словаря"""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            city=data.get('city'),
            street=data.get('street'),
            house_number=data.get('house_number'),
            postal_code=data.get('postal_code')
        )

