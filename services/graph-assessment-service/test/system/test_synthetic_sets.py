'''
The whole run against every synthetic set.

Every folder data/synthetic/<task>/<set>/ holds a submission.json and an
expected.json with what a run has to produce for it. src/start.py runs once
per task with all its sets (config.RUN_ALL_SETS), the way a user starts it,
and every set is compared field by field:

    classes          per class: instances, claims, consequences
    points           total and the deduction per class
    sentences        the feedback, word for word and in order
    transformations  name and variant of every transformation found
                     (none if the field is missing)
    rejected         part of the rejection reason (only rejected sets)
    covers           the catalog codes the set is meant to show -- each one
                     has to be among the classes found

A new set needs no code here: a folder with both files is picked up.
'''

import io
import json
import runpy
from collections import Counter
from contextlib import redirect_stdout

import pytest

from src import config
from src.config import DATA_DIR, SERVICE_DIR
from src.loading import iter_all_datasets

TASKS = sorted(path.name for path in DATA_DIR.iterdir() if (path / "reference.json").is_file())

SETS = [(task, name) for task in TASKS
        for name, _path in iter_all_datasets(DATA_DIR / task)]


@pytest.fixture(scope="module")
def runs():
    '''{task: {set name: Result}} -- each task run once, on first request.'''
    done = {}

    def results_of(task):
        if task not in done:
            done[task] = _run(task)
        return done[task]

    return results_of


def _run(task):
    '''src/start.py over all sets of one task, quietly; config is put back afterwards.'''
    task_dir = DATA_DIR / task
    settings = {
        "TASK": task,
        "TASK_DIR": task_dir,
        "REFERENCE_PATH": task_dir / "reference.json",
        "RUN_ALL_SETS": True,
        "SUBMISSION_FILE": None,
        "COLLECT_GLOSSARY": False,
    }

    with pytest.MonkeyPatch.context() as patch:
        for name, value in settings.items():
            patch.setattr(config, name, value)

        with redirect_stdout(io.StringIO()):
            scope = runpy.run_path(str(SERVICE_DIR / "src" / "start.py"))

    return scope["results"]


@pytest.mark.parametrize(("task", "name"), SETS, ids=[f"{task}/{name}" for task, name in SETS])
def test_set_matches_expected(runs, task, name):
    expected = json.loads((DATA_DIR / task / name / "expected.json").read_text(encoding="utf-8"))
    result = runs(task)[name]

    assert _classes(result) == expected["classes"]
    assert _points(result) == expected["points"]
    assert list(result.sentences) == expected["sentences"]
    assert _transformations(result) == expected.get("transformations", [])

    if "rejected" in expected:
        assert result.rejection is not None, "expected a rejection"
        assert expected["rejected"] in str(result.rejection)
    else:
        assert result.rejection is None, f"rejected: {result.rejection}"

    codes = {instance["code"] for instance in result.classes}
    assert set(expected["covers"]) <= codes, f"not covered: {set(expected['covers']) - codes}"


def _classes(result):
    '''Per class (or name, for an instance without a catalog entry): the three counts.'''
    counted = {}

    for instance in result.classes:
        row = counted.setdefault(instance["class"] or instance["name"], Counter())
        row["instances"] += 1
        row["claims"] += len(instance["claims"])
        row["consequences"] += len(instance["consequences"])

    return {key: dict(row) for key, row in counted.items()}


def _points(result):
    if result.points is None:
        return None

    return {"total": result.points["total"],
            "deductions": {row["class"]: row["deduction"] for row in result.points["deductions"]}}


def _transformations(result):
    return [{"name": found.name, "variant": found.variant} for found in result.transforms]
