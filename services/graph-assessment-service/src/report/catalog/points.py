'''
The scoring: what the diff costs.

    deductions(instances, scoring, task, maximum)

Reads the class instances (-> classify.py) against the notation's scoring
(-> src/notation/catalog.py) and computes the deduction per class: once per
set or per instance, with a cap. The result is a dict the run stores in
Result.points.

What costs nothing:

    - an allowed transformation ("verdict": "accepted") -- it is not an error
    - a class without an entry in the scoring -- reported, not scored; it is
      still in the list, with deduction 0
    - an instance resting on an assumption, if the scoring says
      "vorbehalt": "keiner" -- then only the follow-up question remains

Deductions are counted per class, not per op: three missing keys are one
"primary keys not marked", which is how a grader counts it too.

The scoring dict is the parsed catalog of the notation and keeps its keys
("klassen", "vorbehalt", "modus", "abzug", "deckel", "je_set") as they are in
the notation file.
'''


def deductions(instances, scoring, task=None, maximum=None):
    '''
    The deduction for one submission -- or None if the notation has no
    scoring.

        max         the reachable points: "maximum" if the run passes one
                    (-> config.MAX_POINTS, python -m src.start --points),
                    otherwise the task's value from the scoring; or None
        deductions  per error class found: class, code, name, instances,
                    mode, deduction, scored (does it have points in the catalog?)
        total       all deductions together
        remaining   max minus total, not below 0; None without max
        accepted    the classes of the allowed transformations (class, code,
                    name) -- they cost nothing but are listed so it is visible
                    what was let through
    '''
    if scoring is None:
        return None

    rules = scoring.get("klassen", {})
    counted = _errors_by_class(instances, scoring.get("vorbehalt", "voll"))
    rows = []

    for class_id, found in counted.items():
        rule = rules.get(class_id)
        rows.append({
            "class": class_id,
            "code": found["code"],
            "name": found["name"],
            "instances": found["instances"],
            "mode": rule["modus"] if rule else None,
            "deduction": _deduction(rule, found["instances"]),
            "scored": rule is not None,
        })

    maximum = maximum if maximum is not None else (scoring.get("max") or {}).get(task)
    total = sum(row["deduction"] for row in rows)

    return {
        "max": maximum,
        "deductions": rows,
        "total": total,
        "remaining": None if maximum is None else max(maximum - total, 0),
        "accepted": _accepted(instances),
    }


def _deduction(rule, count):
    '''The deduction by mode: once, or per instance up to the cap.'''
    if rule is None:
        return 0

    if rule["modus"] == "je_set":
        return rule["abzug"]

    return min(rule["abzug"] * count, rule.get("deckel", rule["abzug"] * count))


def _accepted(instances):
    '''The allowed transformations per class, sorted by catalog ID.'''
    seen = {}

    for instance in instances:
        if instance.get("verdict") == "accepted" and instance.get("class"):
            seen.setdefault(instance["class"], {"class": instance["class"],
                                                "code": instance.get("code"),
                                                "name": instance.get("name") or instance["class"]})

    return [seen[class_id] for class_id in sorted(seen)]


def _errors_by_class(instances, reservation):
    '''
    The error instances counted per class -- {class: {code, name, instances}},
    in order of first appearance. Allowed transformations, instances without
    a catalog entry and -- with "keiner" -- instances resting on an assumption
    stay out.
    '''
    counted = {}

    for instance in instances:
        class_id = instance.get("class")

        if class_id is None or instance.get("verdict") == "accepted":
            continue

        if reservation == "keiner" and instance.get("on_assumption"):
            continue

        row = counted.setdefault(class_id, {"code": instance.get("code"),
                                          "name": instance.get("name") or class_id, "instances": 0})
        row["instances"] += 1

    return counted
