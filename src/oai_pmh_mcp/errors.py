"""Typy wyjątków mapowane na warstwy protokołu / transportu OAI-PMH."""

from __future__ import annotations


class OaiError(Exception):
    """Bazowy wyjątek biblioteki."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class OaiProtocolError(OaiError):
    """Repozytorium zwróciło <error code=...> (poza noRecordsMatch)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message or code, code=code)


class OaiHttpError(OaiError):
    """Problem transportowy: timeout, DNS, 4xx/5xx (po wyczerpaniu prób)."""


class OaiParseError(OaiError):
    """Odpowiedź nie jest poprawnym dokumentem OAI-PMH."""
