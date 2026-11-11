'''
Turning a file into a graph.

Three functions, one job -- they only differ in what an error triggers:

    load_graph       the three gates, raises GraphInputError
    read_graph       calls load_graph and catches the error: returns (graph, error)
    load_reference   calls read_graph and stops the run on an error

The error texts end up in the feedback and stay German.
'''

import json
from pathlib import Path

from .checks import WRONG_KIND, GraphInputError, check_file_format
from .convert import nx_from_dict


def load_graph(path, notation, file_format):
    '''
    Reads a JSON file, checks it and builds a networkx graph from it.

    notation     the notation: what the graph structure may carry
    file_format  the exchange format: how the file has to be built

    The three gates are in the code below. First the data format, then the
    graph -- so a format error is caught before the data is processed.
    Errors come as GraphInputError with the file name in front; they name
    their rule (error.rule) and their gate (error.gate).
    '''
    path = Path(path)

    # Gate 1: the file itself -- readable, text, JSON?
    # What cannot be read is not a notation file but something else: an
    # image, a PDF, nothing at all. That is the wrong kind of diagram, not a
    # violation of the format, so it has its own rule.
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise GraphInputError(f"{path.name}: nicht lesbar", WRONG_KIND, 1) from None
    except UnicodeDecodeError:
        raise GraphInputError(f"{path.name}: keine Textdatei", WRONG_KIND, 1) from None
    except json.JSONDecodeError as error:
        raise GraphInputError(f"{path.name}: kein gültiges JSON ({error})",
                              WRONG_KIND, 1) from None

    # Gates 2 and 3 are kept apart even though they reject the same way: only
    # then is it clear afterwards which of the two it was. Both name the same
    # rule (format violation), and only this place knows the number.
    # Prepend the file name, keep the rule -- otherwise it gets lost when the
    # error is wrapped.

    # Gate 2: the exchange format (-> checks.py)
    try:
        check_file_format(data, file_format)
    except GraphInputError as error:
        raise GraphInputError(f"{path.name}: {error}", error.rule, 2) from None

    # Gate 3: the graph -- IDs, edge ends (-> convert.py)
    try:
        return nx_from_dict(data, notation)
    except GraphInputError as error:
        raise GraphInputError(f"{path.name}: {error}", error.rule, 3) from None


def read_graph(path, notation, file_format):
    # Called by start.py, returns (graph, error) -- the graph is None if there
    # was an error. Errors are GraphInputError, the rule is in error.rule.
    try:
        return load_graph(path, notation, file_format), None
    except GraphInputError as error:
        return None, error


def load_reference(path, notation, file_format):
    # Called by start.py, stops the run on an error.
    graph, error = read_graph(path, notation, file_format)

    if error:
        raise SystemExit(f"Abbruch - Reference nicht verwendbar: {error}")

    return graph
