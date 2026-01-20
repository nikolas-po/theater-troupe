"""
Модели данных для театральной системы.
"""
from .actor import Actor
from .author import Author
from .director import Director
from .play import Play
from .production import Production
from .performance import Performance
from .rehearsal import Rehearsal
from .role import Role
from .theatre import Theatre
from .location import Location

__all__ = [
    'Actor',
    'Author',
    'Director',
    'Play',
    'Production',
    'Performance',
    'Rehearsal',
    'Role',
    'Theatre',
    'Location',
]
