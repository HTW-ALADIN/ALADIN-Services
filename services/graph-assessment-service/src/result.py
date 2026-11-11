from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Result:
    '''
    Central data object for one input (reference or submission) per run.

    Every pipeline step (src/*) writes its result into a dedicated field.
    There are no generic data containers; the state of the input can be read
    directly from the fields that are filled.

    Pipeline mapping:
      - src/loading                 -> graph / rejection
      - src/loading/validate.py     -> violations (notation errors, gate 4)
      - src/mapping/isomorphism     -> isomorphic
      - src/mapping                 -> mapping
      - src/report/diff.py          -> deviations (structural errors vs. reference)
      - src/transform               -> transforms (transformations: built differently, not counted as wrong)
      - src/report/sentences.py     -> sentences
      - src/report/catalog          -> classes (the same ops, read as error classes)
      - src/report/catalog/points.py -> points (what it costs, by the notation's scoring)
      - src/report/glossary.py      -> open_questions
    '''

    # --- Basic data & parsing ---
    name: str                 # "Reference" or the name of the set (e.g. "001")
    graph: Any = None         # nx graph of the input (None if rejected)
    rejection: Any = None     # reason for rejection from gates 1-3 (None = loaded successfully)

    # --- Notation check (independent of the reference) ---
    violations: list = field(default_factory=list)  # violations of the notation (gate 4)

    # --- Comparison with the reference ---
    # None means "not checked" (e.g. on rejection or for the reference itself)
    isomorphic: Optional[bool] = None
    mapping: Any = None       # Mapping object (src/mapping.Mapping)
    deviations: list = field(default_factory=list)  # deviations from the reference (op list)
    transforms: list = field(default_factory=list)  # transformations (src/transform.Transform)
    sentences: list = field(default_factory=list)   # 'deviations' as human-readable sentences
    classes: list = field(default_factory=list)     # 'deviations' as class instances (src/report/catalog)
    points: Any = None        # the deduction by the scoring (src/report/catalog/points.py); None without scoring

    # --- Manual clarification ---
    open_questions: list = field(default_factory=list)  # mapping questions that cannot be decided (not errors!)

    @property
    def loaded(self) -> bool:
        '''
        True if the file was found, parsed and not rejected (gates 1-3).
        Says nothing about notation conformity or the reference comparison.
        '''
        return self.rejection is None

    @property
    def conforms(self) -> bool:
        '''
        True if loaded successfully AND free of notation errors (gate 4).
        Says nothing about agreement in content with the reference.
        '''
        return self.loaded and len(self.violations) == 0

    @property
    def compared(self) -> bool:
        '''
        True if this input was compared with the reference.
        Only then do 'isomorphic', 'mapping' and 'deviations' hold valid statements.
        '''
        return self.isomorphic is not None
