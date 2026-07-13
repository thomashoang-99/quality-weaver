from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter
from ruamel.yaml import YAML

from quality_weaver.models import Viewpoint

_VIEWPOINT_LIST = TypeAdapter(list[Viewpoint])


@dataclass(frozen=True)
class _Group:
    name: str
    file: str
    entity_types: frozenset[str]
    risks: frozenset[str]


class Catalog:
    """A validated viewpoint inventory and its deterministic routing index."""

    def __init__(self, version: str, groups: tuple[_Group, ...], viewpoints: list[Viewpoint]):
        self.version = version
        self._groups = groups
        self._viewpoints = tuple(viewpoint.model_copy(deep=True) for viewpoint in viewpoints)
        self._by_id = {viewpoint.id: viewpoint for viewpoint in self._viewpoints}

    @property
    def viewpoints(self) -> tuple[Viewpoint, ...]:
        """Return snapshots so caller mutation cannot corrupt catalog state."""
        return tuple(viewpoint.model_copy(deep=True) for viewpoint in self._viewpoints)

    @classmethod
    def load(cls, root: Path) -> "Catalog":
        """Load catalog metadata and every declared viewpoint document under *root*."""
        metadata = _load_yaml(root / "catalog.yaml")
        if not isinstance(metadata, Mapping):
            raise ValueError("catalog.yaml must contain a mapping")
        version = metadata.get("version")
        raw_groups = metadata.get("groups")
        if not isinstance(version, str) or not isinstance(raw_groups, list):
            raise ValueError("catalog.yaml requires string version and list groups")

        groups: list[_Group] = []
        viewpoints: list[Viewpoint] = []
        group_names: set[str] = set()
        for raw_group in raw_groups:
            group = _parse_group(raw_group)
            if group.name in group_names:
                raise ValueError(f"duplicate catalog group: {group.name}")
            group_names.add(group.name)
            groups.append(group)

            path = _catalog_child(root, group.file)
            document = _load_yaml(path)
            loaded = _VIEWPOINT_LIST.validate_python(document)
            if any(viewpoint.group != group.name for viewpoint in loaded):
                raise ValueError(f"viewpoint group does not match catalog group: {group.name}")
            viewpoints.extend(loaded)

        ids = [viewpoint.id for viewpoint in viewpoints]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate viewpoint id")
        return cls(version, tuple(groups), viewpoints)

    def route(
        self,
        entity_types: set[str],
        risks: set[str],
        enabled_groups: set[str],
    ) -> set[str]:
        """Return groups selected by entity type, risk signal, or explicit enablement."""
        normalized_entities = {value.casefold() for value in entity_types}
        normalized_risks = {value.casefold() for value in risks}
        normalized_groups = {value.casefold() for value in enabled_groups}
        return {
            group.name
            for group in self._groups
            if group.name.casefold() in normalized_groups
            or bool(group.entity_types & normalized_entities)
            or bool(group.risks & normalized_risks)
        }

    def get(self, viewpoint_id: str) -> Viewpoint:
        """Return one viewpoint or raise a descriptive ``KeyError``."""
        try:
            return self._by_id[viewpoint_id].model_copy(deep=True)
        except KeyError:
            raise KeyError(f"unknown viewpoint: {viewpoint_id}") from None


def _load_yaml(path: Path) -> Any:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))


def _parse_group(raw_group: Any) -> _Group:
    if not isinstance(raw_group, Mapping):
        raise ValueError("each catalog group must be a mapping")
    name = raw_group.get("name")
    file = raw_group.get("file")
    entity_types = raw_group.get("entity_types", [])
    risks = raw_group.get("risks", [])
    if not isinstance(name, str) or not isinstance(file, str):
        raise ValueError("catalog group requires string name and file")
    if not _is_string_list(entity_types) or not _is_string_list(risks):
        raise ValueError("catalog group entity_types and risks must be string lists")
    return _Group(
        name=name,
        file=file,
        entity_types=frozenset(value.casefold() for value in entity_types),
        risks=frozenset(value.casefold() for value in risks),
    )


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _catalog_child(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    resolved_root = root.resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError(f"catalog file escapes root: {relative_path}")
    return candidate
