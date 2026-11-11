# Starts the program: python -m src.start

# --- Imports ---------------------------

from pathlib import Path

# Settings: the run
from src import config

# Input, checks, result:
from src.report.catalog import deductions, classify, classify_rejection
from src.report import deviations
from src.report import observe, open_questions, update_glossary
from src.mapping import build_mapping
from src.mapping.isomorphism import is_isomorphic
from src.loading import (get_submission_path, iter_all_datasets, load_reference, read_graph)
from src.result import Result
from src.terminal_output import show_info, show_report, show_result, show_warnings
from src.report import describe, describe_rejection
from src.loading import validate
from src.transform import find_transforms
from src.notation import load_catalog, load_file_format, load_notation, load_transforms




# --- Load ------------------------------


# Load the notation.
# four files under notations/<NOTATION>/
notation = load_notation(config.NOTATION)        # .notation.json           what may be drawn (+ units, rules)
file_format = load_file_format(config.NOTATION)  # .austauschformat.json    what the file has to look like (optional)
catalog = load_catalog(config.NOTATION)          # .fehlerkatalog.json      error classes (catalog, scoring, feedback)
transforms = load_transforms(config.NOTATION)    # .umformungen.json        when two diagrams build the same thing differently




# --- Start -----------------------------


# Preparation
# Builds the list of sets to check, based on the config.

# Check a single submission file (config.SUBMISSION_FILE)
if config.SUBMISSION_FILE:
    submission_path = Path(config.SUBMISSION_FILE)
    datasets = [(submission_path.parent.name, submission_path)]

# Go through all sets in the task folder (config.RUN_ALL_SETS, config.TASK_DIR)
elif config.RUN_ALL_SETS:
    datasets = list(iter_all_datasets(config.TASK_DIR))

# Check only one set in the task folder (default set, config.DEFAULT_SET)
else:
    submission_path = get_submission_path(config.TASK_DIR, config.DEFAULT_SET)
    datasets = [(config.DEFAULT_SET, submission_path)]


print("ERD-Vergleich")
print()

show_info(notation)    # show the info block
show_warnings()       # what stands out about the notation (-> src/notation/warnings.py)




# --- Reference -------------------------

# Load the reference
# - returns only the bare nx.MultiGraph
# - stops hard if the input is broken.
reference_graph = load_reference(
    config.REFERENCE_PATH,
    notation,
    file_format
)

# Initialise the Result object with the loaded graph
reference = Result("Reference", graph=reference_graph)

# Validate the reference graph and attach any violations to the reference object
reference.violations = validate(reference.graph, notation, notation.rules["connected"])

# Terminal output for the reference (size and notation findings)
show_result(reference)




# --- Submissions -----------------------


# Two collectors that outlive the loop. Every round stores here what someone
# needs afterwards: the summary and the label list only run AFTER the loop
# over all sets.
results = {}        # set_name -> Result              -> show_report, at the bottom
observations = {}   # set_name -> (pairs, unresolved) -> update_glossary (only COLLECT_GLOSSARY)


# Go through the list of sets (may be just the default set).
for set_name, submission_path in datasets:


    # LOAD
    # Read the file.
    # (A format error rejects this one submission, the run goes on with the others.)
    graph, error = read_graph(submission_path, notation, file_format)
    result = Result(set_name, graph=graph, rejection=error)
    results[set_name] = result

    if not result.loaded:
        # REJECTED, carry on -- but not silently: the rejection names its own
        # rule (-> src/loading/checks.py), and the catalog lists it. Nothing
        # is compared, there is no graph.
        result.classes = classify_rejection(catalog, error)
        result.points = deductions(result.classes, catalog.scoring, config.TASK, config.MAX_POINTS)
        result.sentences = describe_rejection(result.classes, catalog)

        show_result(result)
        continue



    # VALIDATE
    # Check the notation. A violation is noted.
    result.violations = validate(result.graph, notation, notation.rules["connected"])



    # FULL ISOMORPHISM
    # Compare the submission with the reference
    # Isomorphism (only true/false, labels are ignored)
    result.isomorphic = is_isomorphic(reference.graph, result.graph, notation)



    # MAPPING
    # Pairing between reference and submission -- the eight steps in
    # src/mapping (anchors -> piece -> group -> name decides -> again ->
    # softer anchors -> interchangeable -> rest; the name stages: src/mapping/labels).
    result.mapping = build_mapping(reference.graph, result.graph, notation)



    # TRANSFORMATIONS
    # Where the submission built the same thing differently (attribute instead
    # of IS-A, entity instead of relationship) -- searched on what the mapping
    # left open. -> src/transform
    result.transforms = find_transforms(reference.graph, result.graph, result.mapping,
                                        transforms, notation=notation)



    # The diff: the deviations as ops, derived from the mapping.
    # What happens to the cases left open is up to the switch
    # (-> config.AMBIGUOUS_AS_OPS).
    result.deviations = deviations(reference.graph, result.graph, result.mapping, notation,
                                   config.AMBIGUOUS_AS_OPS)



    # The catalog: the same ops, read as error classes -- which of them
    # together are ONE error and what it is called (src/report/catalog).
    # The diff itself does not change.
    result.classes = classify(result.deviations, reference.graph, result.graph,
                              result.mapping, result.violations, notation, catalog,
                              result.transforms)



    # What it costs: per class the deduction from the notation's scoring
    # ("punkte" per class in the notation's catalog). Without points it stays None.
    # The reachable points come from the same catalog, unless they are passed
    # at start (-> config.MAX_POINTS, python -m src.start --points).
    result.points = deductions(result.classes, catalog.scoring, config.TASK, config.MAX_POINTS)



    # The same deviations as sentences. Not a step of its own -- a renderer
    # over the op list that adds nothing and leaves nothing out. Where the
    # catalog has a template for a class, ONE sentence is said per instance
    # (a transformation: one line, not twenty); the rest unit by unit.
    result.sentences = describe(result.deviations, reference.graph, result.graph,
                                instances=result.classes, catalog=catalog)




    # Read off the labels -- what is called what here?
    # Two things from the same source: the list that grows across runs, and
    # the questions to the student about what is not proven.
    pairs, unresolved = observe(reference.graph, result.graph, result.mapping)
    result.open_questions = open_questions(pairs, unresolved)
    observations[set_name] = (pairs, unresolved)

    show_result(result)





# --- Report ----------------------------

show_report(results.values())


# Write the label list if the flag is set and there were observations.
if config.COLLECT_GLOSSARY and observations:
    update_glossary(config.GLOSSARY_PATH, config.TASK, observations)


# ----------------------------------
# From here on these are available -- to anyone who runs this module via
# runpy.run_path and reads its globals:
#   reference    Result of the reference (reference.graph is the nx.MultiGraph)
#   results      set_name -> Result of the submission
#   datasets     [(set_name, path of the submission)] -- the list built above
#   notation     the notation, catalog the error catalog, transforms the transformations
#
# Per Result (src/result.py) -- what the steps filled in:
#   .graph           nx.MultiGraph, None if rejected
#   .rejection       reason for rejection, None if loaded
#   .violations      notation violations (empty == conforming)
#   .isomorphic      isomorphic to the reference? None == not checked
#   .mapping         the pairing (src/mapping.Mapping)
#   .deviations      the deviations as ops (src/report/diff.py)
#   .transforms      the transformations (src/transform), rank 1 in the catalog
#   .sentences       the same deviations as sentences (src/report/sentences.py, PRINT_FEEDBACK)
#   .classes         the same deviations as class instances (src/report/catalog)
#   .points          the deduction for them (src/report/catalog/points.py), None without scoring
#   .open_questions  what is not proven, as a question (src/report/glossary.py)
#
# Plus three yes/no questions to the same Result, each over different fields:
#   .loaded      is there a graph?             (from .rejection)
#   .conforms    notation followed?            (from .violations)
#   .compared    was it compared at all?       (from .isomorphic)
