'''
The knowledge base: fetch it once, then it lives here.

    wordnet/     the wordnet (OdeNet) as a database of the library "wn"
                 python -m src.knowledge.wordnet    -> wordnet/data/wn.db

Plus the lemma list, which is built from the wordnet and lives next to the
normalization:
                 python -m src.mapping.labels.normalization.lang.build_lemmas
                                                    -> normalization/lang/data/lemmas-de.json

Not a runtime path: a run that fetches data along the way is not repeatable.
At runtime -> src/mapping/labels/semantics/resources.py reads from here;
where the knowledge base lives is entered as a ResourceSpec by
-> src/mapping/labels/label_match.py. $SEMANTICS_WN_DATA overrides the path.
Without the data the name stage "synonym" drops out, the rest keeps running.
'''
