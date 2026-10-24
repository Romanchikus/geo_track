from dataclasses import dataclass

from fastapi import Query


@dataclass(slots=True)
class Page:
    limit: int
    offset: int


def get_page(
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
) -> Page:
    return Page(limit=limit, offset=offset)
