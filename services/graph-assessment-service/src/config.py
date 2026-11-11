import argparse
import sys
from pathlib import Path

from src.loading import get_reference_path

SERVICE_DIR = Path(__file__).resolve().parent.parent     # service directory (base for relative paths)


def rel_path(path):
    '''
    The path relative to the service directory -- or in full if it lies outside.

    Every printed path goes through here (-> src/terminal_output.py).
    Otherwise every report would show the folder it happened to be created in.
    '''
    try:
        return Path(path).relative_to(SERVICE_DIR).as_posix()
    except ValueError:
        return Path(path).as_posix()


# ----------------------------------
# Which notation is checked against?

NOTATION = "erd_schlageter"    # the prefix of its files in notations/<NOTATION>/

MAX_POINTS = None              # The reachable points of the task. None means: the value from
                               # the notation's error catalog ("bewertung.max", per task;
                               # -> src/report/catalog/points.py). Both can be passed at
                               # start -- see the bottom of this file.


# ----------------------------------
# Which data does a run use?

DATA_DIR = SERVICE_DIR / "data" / "synthetic"       # one folder per reference (task)

TASK = "bank"                                       # Which task? The folder name under DATA_DIR
RUN_ALL_SETS = False                                # All sets (True) or only DEFAULT_SET (False)?
DEFAULT_SET = "binary_for_ternary"                  # Used with RUN_ALL_SETS = False: the folder
                                                    # name of the submission in the task folder

# Single files instead of the task folder. Empty means: what is set above
# applies (TASK + RUN_ALL_SETS/DEFAULT_SET).
REFERENCE_FILE = None       # e.g. DATA_DIR / "bank" / "reference.json"
SUBMISSION_FILE = None      # e.g. DATA_DIR / "bank" / "key_wrong_reversed" / "submission.json";
                            # the folder name is the set name

# Derived -- do not change by hand
TASK_DIR = DATA_DIR / TASK                                          # reference + one folder per submission
REFERENCE_PATH = REFERENCE_FILE or get_reference_path(TASK_DIR)


# ----------------------------------
# What to do when the pairing stays ambiguous?

AMBIGUOUS_AS_OPS = True
# True   The reference node is written as "missing", its candidates as
#        "extra" -- marked as an assumption ("assumed"). The diff then always
#        reaches the reference, but claims a pairing that is not proven.
#        -> src/report/diff.py, deviations()
# False  No op. The diff stays silent there and does not reach the reference.
#
# In the terminal it reads like this (-> src/report/sentences.py, _open_case_sentence):
#   * Zu Attribut »Datum« passten »Zeitpunkt« und »Zeitpunkt«, belegt ist
#     keine Zuordnung -- so gelesen fehlt »Datum«, und die genannten sind zu viel


# ----------------------------------
# Which stages of the knowledge base run?

SEMANTIC_STAGES = ("syn_wordnet",)
# The methods allowed to answer "do two labels say the same thing?" -- in
# the order they are asked. An empty tuple switches semantics off entirely;
# then only normalization is left of the four label questions
# (-> src/mapping/labels/label_match.py).
#
# The registry has three stages (-> src/mapping/labels/semantics/stages.py),
# one of them runs by default:
#
#   syn_wordnet     synonymy via the synsets of the wordnet -- "Ort"/
#                   "Standort". The default, and the only one switched on.
#   hyper_wordnet   hypernyms/hyponyms. Built, but off: it found one correct
#                   pair (Auto/Fahrzeug) against three questionable ones (ID/Name).
#   wup_wordnet     taxonomic similarity after Wu-Palmer. Off: its threshold
#                   0.85 was tuned on the same data it was evaluated on.
#
# Switching also works after import: label_match rebuilds its methods when
# this value has changed.

# ----------------------------------
# Output

PRINT_INFO = True           # info block at program start
PRINT_FEEDBACK = True       # deviations as sentences, deduction and follow-up questions -- the feedback
                            # (src/report/sentences.py, src/report/glossary.py)


# ----------------------------------
# The label list (src/report/glossary.py)

COLLECT_GLOSSARY = False                            # update the list during the run
GLOSSARY_PATH = SERVICE_DIR / "glossary" / f"{TASK}.json"

# Two files: GLOSSARY_PATH (for every reference label, all the names students
# used for it) and <task>_questions.json next to it (the questions per set).
# Only what this run produces is overwritten: its sets are first removed from
# both files and then written anew, everything else stays; an entry without a
# remaining set is dropped. The list is never read back -- it does not flow
# into any run.


# ----------------------------------
# Two values can be passed at start, everything else is set in this file:
#
#     python -m src.start --notation erd_schlageter --points 30
#
# The command line is only read when start.py runs. Under pytest and in a
# child process (python -c) sys.argv holds something else -- then the values
# above apply. This lives here and not in start.py because three modules
# read config.NOTATION at import time (-> src/report/wording.py,
# src/report/catalog/classify.py, src/notation/diagram/units.py); an override
# after the src imports would come too late for them.

if Path(sys.argv[0]).name == "start.py":
    _parser = argparse.ArgumentParser(
        prog="python -m src.start",
        description="Compares a submission with the reference solution.")
    _parser.add_argument("--notation", default=NOTATION, metavar="NAME",
                         help=f"notation under notations/ (default: {NOTATION})")
    _parser.add_argument("--points", type=int, default=MAX_POINTS, metavar="N",
                         help="reachable points of the task "
                              "(default: from the notation's error catalog)")
    _cli = _parser.parse_args()
    NOTATION, MAX_POINTS = _cli.notation, _cli.points
