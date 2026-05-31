from typing import TypeVar, Type, Any

T = TypeVar('T')

class World:
    def __init__(self):
        self._next_entity_id = 0
        self._components: dict[Type, dict[int, Any]] = {}

    def create_entity(self) -> int:
        entity = self._next_entity_id
        self._next_entity_id += 1
        return entity

    def add_component(self, entity: int, component: Any):
        comp_type = type(component)
        if comp_type not in self._components:
            self._components[comp_type] = {}
        self._components[comp_type][entity] = component

    def get_component(self, entity: int, comp_type: Type[T]) -> T | None:
        return self._components.get(comp_type, {}).get(entity)

    def get_components(self, *comp_types: Type) -> list[tuple[int, list[Any]]]:
        if not comp_types:
            return []
        
        base_entities = set(self._components.get(comp_types[0], {}).keys())
        for comp_type in comp_types[1:]:
            base_entities &= set(self._components.get(comp_type, {}).keys())
        
        result = []
        for ent in base_entities:
            result.append((ent, [self._components[ct][ent] for ct in comp_types]))
        return result
