'''
Where the files of a task live.

The data is sorted by task and submission:

    <task>/reference.json             the reference solution, once per task
    <task>/<set>/submission.json      one submission, one folder per set

The folder name IS the name of the set ("001", "060"). This layout is in no
notation file, because it describes the data and not what is drawn -- so it
lives here and nowhere else.

This module does not decide which task is meant: the folder comes in as
"task_dir" (-> config.py, TASK_DIR).
'''

from pathlib import Path

REFERENCE_FILE = "reference.json"
SUBMISSION_FILE = "submission.json"


def get_reference_path(task_dir):
    '''The path to the reference file of the task.'''
    return Path(task_dir) / REFERENCE_FILE


def get_submission_path(task_dir, set_name):
    '''The path to the submission of a given set.'''
    return Path(task_dir) / str(set_name) / SUBMISSION_FILE


def iter_all_datasets(task_dir):
    '''
    All sets of the task: (set_name, submission_path), in order.

    Sorted, so a run always has the same order. A folder without a submission
    file is skipped -- it is not a set.
    '''
    task_dir = Path(task_dir)

    for set_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
        submission_path = set_dir / SUBMISSION_FILE

        if submission_path.is_file():
            yield set_dir.name, submission_path
