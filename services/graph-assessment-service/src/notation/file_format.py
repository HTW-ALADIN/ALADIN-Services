'''
The exchange format: notations/<NOTATION>/<name>.austauschformat.json.

A JSON schema for the structure of a graph file -- which fields it may carry
and which it must carry. It is checked at gate 2
(-> src/loading/checks.py: check_file_format).

Without the file an empty dict -- then nobody checks the file format, and
everything that can be turned into a graph gets through. What the notation
does not allow still shows up later (-> src/loading/validate.py); only the
rejection for a format violation is dropped.
'''

from . import files


@files.cached
def load_file_format(name):
    '''The exchange format of the notation -- an empty dict without the file.'''
    return files.read(name, "file_format", optional=True) or {}
