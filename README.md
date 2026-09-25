# ETKAD Workflow Maps

Three maps of research workflows. They are not three versions of one thing —
each has a different unit, a different corpus, and answers a different
question. Listed oldest to newest.

| | Built | A dot is | Corpus | Answers |
|---|---|---|---|---|
| [tool-galaxy/](tool-galaxy/) | 5 Aug 2026 | a software tool | 1,138 bioinformatics workflows → 632 tools | which tools are used together |
| [method-galaxy/](method-galaxy/) | 6 Aug 2026, morning | a method (and, in a second view, an object) | 6,305 SSH Open Marketplace items, 2,366 tagged | which DH methods co-occur, and which ones Estonia does not use |
| [workflow-galaxy/](workflow-galaxy/) | 6 Aug 2026, afternoon | a workflow | 240 workflows: 108 Marketplace + 119 Programming Historian + 13 ETKAD | which workflows resemble each other, and in what respect |

Workflow Galaxy is the only map whose unit is the thing ETKAD actually
publishes. Open `workflow-galaxy/workflow_galaxy.html`; the method behind it
is documented in `workflow-galaxy/how_it_works.html`.

A one-page index linking all three maps, with an explanation of how they
overlap, is at [`index.html`](index.html).

## Why all three are kept

None of these maps supersedes another, because their data does not overlap:

- **tool-galaxy** is the only tool-level map and the only life-science
  corpus. It tested whether co-usage → proximity works as a technique, and
  is where a future tool layer for Workflow Galaxy would come from. Its 632
  tool nodes have no counterpart in the other two maps.
- **method-galaxy** is the only map of the method vocabulary itself, and the
  only one built from the full 2,366-object Marketplace corpus. Its gap
  report — which methods European DH uses that Estonian workflows do not —
  cannot be reproduced from workflow-galaxy, which sees only 108 of those
  objects.
- **workflow-galaxy** compares whole workflows, matching the unit ETKAD
  actually publishes.

Workflow Galaxy replaced Method Galaxy's role of answering "where does ETKAD
sit", not its contents — Method Galaxy's method-vocabulary coverage and gap
report remain unique to it.

## Versioning

Versions live in git tags, not in directory names. `v1-method-galaxy` pins
the state of Method Galaxy before workflow-galaxy (the whole-workflow map)
was started; `v1-workflow-galaxy` pins the earlier tool-level map, back when
that directory held today's `tool-galaxy/`; `v1-workflow-atlas` pins the
whole-workflow map from before it was renamed from `workflow-atlas/` to
`workflow-galaxy/`. Tags are frozen at creation time and do not follow later
renames, so a tag name and the current directory it once matched can now
diverge — check `git show <tag> --stat` if a tag's contents aren't obvious
from its name.

```bash
git tag                        # what is pinned
git show v1-method-galaxy      # what that state was
git checkout v1-method-galaxy  # go there; git checkout master to come back
```

## Pipelines

All three pipelines follow the same four stages — `1_harvest` → `2_extract`
→ `3_layout` → `4_build_map` — run from inside their own directory, writing
to a local `work/`. All data collection is HTTP requests into memory;
nothing is cloned to disk.
