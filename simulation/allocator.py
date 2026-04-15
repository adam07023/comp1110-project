from __future__ import annotations

from domain.models import Table


def expand_tables(table_inventory: list[tuple[int, int]] | list) -> list[Table]:
    tables: list[Table] = []
    next_id = 1
    for inventory in table_inventory:
        seats = inventory.seats
        count = inventory.count
        for _ in range(count):
            tables.append(Table(table_id=f"T{next_id}", seats=seats))
            next_id += 1
    return tables
