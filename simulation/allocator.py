from __future__ import annotations

from domain.models import Table, TableInventory


def expand_tables(table_inventory: list[tuple[int, int] | TableInventory] | list) -> list[Table]:
    tables: list[Table] = []
    next_id = 1
    for item in table_inventory:
        if isinstance(item, tuple):
            seats, count = item
        else:
            seats, count = item.seats, item.count
        for _ in range(count):
            tables.append(Table(table_id=f"T{next_id}", seats=seats))
            next_id += 1
    return tables
