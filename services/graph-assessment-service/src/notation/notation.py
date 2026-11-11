'''
The notation itself: notations/<NOTATION>/<name>.notation.json.

One file, one reader. What is in it is modelled here with Pydantic:

    node_types       which nodes exist, what they are called in plain words
                     and which values they may carry
    allowed_edges    which edges are allowed, and what may be on them
    equivalents      which values count as meaning the same for the comparison
    units            which reference determines a node in the first place --
                     the block is interpreted by -> src/notation/diagram/units.py
    rules            what the notation requires without it following from the
                     allowed edges (JSON key: "regeln")

Checked at load time, not at the first comparison: a typo in
notations/ERD/erd_schlageter.notation.json shows up at program start. That
also holds for the two blocks units and rules -- they are checked whether
anyone asks for them later or not.

JSON carries no justifications.
'''

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from . import files

#: The rules that exist, and what holds if one is not declared.
#: What is not stated is not required -- the defaults all say no.
#: So far there is one: connected -- must the diagram be connected?
#: If it falls apart into parts that do not touch each other, that is a
#: finding (-> src/loading/validate.py).
RULE_DEFAULTS = {"connected": False}

#: The fields of a unit entry and of a reference -- exactly these, no more.
#: On top of that an entry may say that it is an adornment
#: ("adornment": true): a type that hangs on its owner and carries no
#: skeleton (-> src/notation/diagram/units.py).
UNIT_KEYS = {"anchor", "references"}
OPTIONAL_UNIT_KEYS = {"adornment"}
REFERENCE_KEYS = {"role", "target"}


class PropertySpec(BaseModel):
    '''
    Specification of a node or edge property.

        type     the base type, or None for "any"
        enum     the allowed values, or None for "all"
        tuple    a value of fixed arity, each position again a PropertySpec
        default  what holds when the property is missing

    tuple excludes type and enum; extra="forbid", so that a typo in a field
    name shows up.
    '''

    model_config = ConfigDict(extra="forbid")

    type: Optional[Literal["string", "boolean", "integer", "number"]] = None
    enum: Optional[list[Any]] = None            # None is allowed as an entry
    tuple: Optional[list["PropertySpec"]] = None
    default: Any = None

    @model_validator(mode="after")
    def _consistent(self):
        if self.tuple is not None and (self.type is not None or self.enum is not None):
            raise ValueError("tuple excludes type/enum")

        if self.enum is not None and self.default is not None and self.default not in self.enum:
            raise ValueError(f"default={self.default!r} is not in enum={self.enum!r}")

        return self


class NodeTypeDef(BaseModel):
    '''
    A node type: what it is called in plain words and which properties it may carry.

    "name" is the word the feedback uses to address the type ("Entität") --
    without it the key itself would appear in the sentence ("entity"). It
    lives here because it belongs to the node type and not to the comparison
    (-> src/report/wording.py).
    '''

    name: str = ""
    properties: dict[str, PropertySpec] = Field(default_factory=dict)


class EdgeRule(BaseModel):
    '''
    An allowed edge shape.

    "between" is a pair of type lists and meant undirected: an edge fits if
    its endpoints occupy the two sides in any order. If the same types stand
    on both sides, that also covers the reflexive relationship.
    '''

    between: tuple[list[str], list[str]]
    properties: dict[str, PropertySpec] = Field(default_factory=dict)
    required_properties: dict[str, PropertySpec] = Field(default_factory=dict)


class Notation(BaseModel):
    '''Complete description of a notation.'''

    model_config = ConfigDict(populate_by_name=True)

    name: str
    # The networkx class the graph is built in. The same list is in
    # GRAPH_CLASSES (-> src/loading/convert.py): whoever adds one here adds it
    # there too.
    graph_class: Literal["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"] = "Graph"
    node_types: dict[str, NodeTypeDef]
    edge_properties: dict[str, PropertySpec] = Field(default_factory=dict)
    # How an edge is built is deliberately not stated here: two ends, each
    # only with "id". That is not a choice of the notation but the data
    # structure -- a networkx edge has two ends and nothing else
    # (-> src/loading/convert.py).
    allowed_edges: list[EdgeRule] = Field(default_factory=list)
    # Values that count as meaning the same for the comparison.
    # [["n", "m"]] means: cardinality n and m count as the same value.
    equivalents: list[list[Any]] = Field(default_factory=list)
    # The units: which reference determines a node in the first place.
    # Deliberately raw dicts -- src/notation/diagram, src/mapping and
    # src/transform pass them on unchanged and access them with
    # unit["anchor"]. They are checked below in _check_units and interpreted
    # in src/notation/diagram/units.py.
    units: list[dict[str, Any]] = Field(default_factory=list)
    # What the notation requires without it following from allowed_edges.
    # The key in the file is "regeln"; missing rules get their default from
    # RULE_DEFAULTS below.
    rules: dict[str, Any] = Field(default_factory=dict, alias="regeln")

    @model_validator(mode="before")
    @classmethod
    def _resolve_property_refs(cls, data: Any) -> Any:
        '''
        allowed_edges[*].properties may be a list of names.

        The names are resolved against edge_properties; an unknown name is an
        error. Whoever writes the dict form directly passes through unchanged.
        '''
        if not isinstance(data, dict):
            return data

        table = data.get("edge_properties") or {}
        rules = data.get("allowed_edges")

        if not isinstance(rules, list):
            return data

        for i, rule in enumerate(rules):
            if not isinstance(rule, dict) or not isinstance(rule.get("properties"), list):
                continue

            resolved = {}

            for prop_name in rule["properties"]:
                if prop_name not in table:
                    raise ValueError(
                        f"allowed_edges[{i}].properties: unknown edge property "
                        f"{prop_name!r} (not declared in edge_properties)"
                    )
                resolved[prop_name] = table[prop_name]

            rule["properties"] = resolved

        return data

    @model_validator(mode="after")
    def _edge_types_exist(self):
        '''Every type in allowed_edges must be declared under node_types.'''
        for i, rule in enumerate(self.allowed_edges):
            for side, types in enumerate(rule.between):
                for node_type in types:
                    if node_type not in self.node_types:
                        raise ValueError(
                            f"allowed_edges[{i}].between[{side}]: "
                            f"unknown node type {node_type!r}"
                        )

        return self

    @model_validator(mode="after")
    def _check_units(self, info: ValidationInfo):
        '''
        Block "units": the fields must be right, every anchor and every
        target must be under node_types.

        Which edges may exist is said by allowed_edges. What allowed_edges
        does not say: which side of an edge determines the node in the first
        place and what this reference is called ("owner", "participant").
        That is in the block "units", one entry per anchor type:

            {"anchor": "attribute", "references": [{"role": "owner", "target": [...]}]}

        Without the block the list stays empty -- then the notation knows no
        references and every node stands on its own.
        '''
        known = set(self.node_types)

        for i, unit in enumerate(self.units):
            where = f"{_where(info)} units[{i}]"

            if set(unit) - OPTIONAL_UNIT_KEYS != UNIT_KEYS:
                raise ValueError(f"{where}: expected the fields {sorted(UNIT_KEYS)} "
                                 f"(also allowed: {sorted(OPTIONAL_UNIT_KEYS)}), "
                                 f"found {sorted(unit)}")

            if not isinstance(unit.get("adornment", False), bool):
                raise ValueError(f"{where}: 'adornment' must be true or false")

            if unit["anchor"] not in known:
                raise ValueError(f"{where}: unknown anchor type {unit['anchor']!r}")

            for reference in unit["references"]:
                if set(reference) != REFERENCE_KEYS:
                    raise ValueError(f"{where}.references: expected the fields "
                                     f"{sorted(REFERENCE_KEYS)}, found {sorted(reference)}")

                for target in reference["target"]:
                    if target not in known:
                        raise ValueError(f"{where}.{reference['role']}: "
                                         f"unknown node type {target!r}")

        return self

    @model_validator(mode="after")
    def _fill_rules(self, info: ValidationInfo):
        '''
        Block "regeln": every key a known rule, every value a yes or no.
        Whatever is not stated is at its default.
        '''
        for key, value in self.rules.items():
            where = f"{_where(info)} regeln[{key!r}]"

            if key not in RULE_DEFAULTS:
                raise ValueError(f"{where}: unknown rule, known are {sorted(RULE_DEFAULTS)}")

            if not isinstance(value, bool):
                raise ValueError(f"{where}: expected true or false, found {value!r}")

        self.rules = {**RULE_DEFAULTS, **self.rules}

        return self

    def node_type_names(self) -> list[str]:
        '''The declared node types, in declaration order.'''
        return list(self.node_types)

    def type_names(self) -> dict[str, str]:
        '''
        What a node type is called in plain words -- {"entity": "Entität", ...}.

        A type without "name" is missing here; the sentence then names it by
        its own key (-> src/report/wording.py).
        '''
        return {type_name: definition.name
                for type_name, definition in self.node_types.items() if definition.name}

    def matching_edge_rules(self, type_u: str, type_v: str) -> list[EdgeRule]:
        '''All rules that allow an edge between these two types.'''
        return [
            rule for rule in self.allowed_edges
            if (type_u in rule.between[0] and type_v in rule.between[1])
            or (type_u in rule.between[1] and type_v in rule.between[0])
        ]

    def edge_property_specs(self, type_u: str, type_v: str) -> dict[str, PropertySpec]:
        '''All properties that may be on an edge between these types.'''
        specs = {}

        for rule in self.matching_edge_rules(type_u, type_v):
            specs.update(rule.properties)
            specs.update(rule.required_properties)

        return specs

    def equivalents_for(self, value: Any) -> set:
        '''The equivalence group of a value; if it is in none, it is {value}.'''
        for group in self.equivalents:
            if value in group:
                return set(group)

        return {value}


@files.cached
def load_notation(name):
    '''The notation: node types, allowed edges, equivalences, units, rules.'''
    return Notation.model_validate(files.read(name, "notation"), context={"name": name})


def _where(info):
    '''
    Which file is meant -- for the error texts above.

    load_notation() passes the name of the notation in as context; whoever
    builds the model by hand (tests) gets a placeholder.
    '''
    name = (info.context or {}).get("name", "<notation>")

    return f"{name}{files.SUFFIXES['notation']}"
