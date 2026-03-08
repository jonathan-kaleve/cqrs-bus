from dataclasses import dataclass

from cqrs_bus import Query, QueryHandler


@dataclass
class GetItemQuery(Query):
    item_id: int


class GetItemHandler(QueryHandler[GetItemQuery, str]):
    async def handle(self, query: GetItemQuery) -> str:
        return f"item:{query.item_id}"
