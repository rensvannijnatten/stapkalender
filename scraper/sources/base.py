"""Gemeenschappelijke interface voor alle bronnen."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod

from ..http import PoliteSession
from ..model import Tocht


class Source(ABC):
    #: korte sleutel, bv. "wsvl"
    key: str = ""
    #: waarde voor Tocht.promoter
    promoter: str = ""

    def __init__(self, session: PoliteSession, data_dir: str):
        self.session = session
        self.data_dir = data_dir

    @abstractmethod
    def fetch(self, start: dt.date, end: dt.date) -> list[Tocht]:
        """Alle tochten van start t/m end (inclusief). Gooit een exceptie als de bron kapot is."""
