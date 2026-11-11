'''
src/ -- the path of a submission, as folders. start.py calls the steps in
this order:

    notation/         read the notation: schema, units, declarations
                      (transformations, scoring, type names). The data lives
                      in notations/<NOTATION>/, only the reader is here.
    loading/       1  load and check: JSON -> graph, notation violations
    mapping/       2  pair up: which node of the submission is which node of
                      the reference? -- the eight steps, with isomorphism/ (the
                      structure) and labels/ (the names) below
    transform/     3  find transformations: the same thing built differently
    report/        4  the diff as ops, the same ops as error classes,
                      as sentences and as a label list
    terminal_output.py 5  how the result appears in the terminal

Alongside, not a step:

    result.py         the Result: what is collected about one input. Every
                      step above fills in its field, the output reads them.
                      It belongs to no step, so it lives here.
    knowledge/        the knowledge base (the wordnet) -- fetch it once, then
                      it is there (python -m src.knowledge.wordnet)
    config.py         the settings of a run
    start.py          the entry point (python -m src.start)
'''
