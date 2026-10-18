# Engineering Lessons Learned

This file captures process and architecture lessons intended to change how the next iteration is done.

## Architecture and safety

### 1. Integrity, authenticity, commit attribution, and sufficiency are different
A digest detects changes relative to a trusted expected digest; it does not authenticate the producer.
GitHub workflow/job/artifact metadata anchors platform provenance, but does not automatically prove
that the test assertion was semantically sufficient. Each property needs its own check.

### 2. Keep the deterministic core authoritative
The Phase I state machine must decide if an obligation can pass. LLMs can propose bounded risk
hypotheses; they cannot assign final states, invent commands, or choose the final conclusion. Artifact
fields cannot bypass the same contract.

### 3. Coverage is a negative filter, not proof
A line hit can coexist with the wrong assertion. A happy-path authorization test does not prove
cross-user denial. Reconcile exact test identity with target line/branch coverage and behavioral
sufficiency.

### 4. Inconclusive is a meaningful state
Missing, malformed, stale, skipped, partial, weak, or contradictory evidence must not turn neutral or
success. Human approval and policy waiver are separate and auditable, not alternate spellings for a
machine pass.

### 5. Recheck at the external side-effect boundary
A PR can change while evidence is being downloaded or parsed. Re-check base/head/open state after
collection and immediately before publishing. A check early in a worker does not close the race window.

## Implementation and debugging

### 6. CI applies to one exact SHA
A green run on a parent cannot certify new code. Report which jobs ran for the exact SHA. When a run
fails at formatting/lint, mypy, tests, and coverage are skipped—not implicitly passed.

### 7. Stop guessing at lint output
Phase III spent too many iterations manually flipping imports for Ruff `I001` in
`tests/unit/test_evidence_ledger.py`; CI still failed on the same block. Reproduce the configured
Ruff version, apply its exact auto-fix diff, inspect the result, commit it, verify the branch pointer,
then rerun.

### 8. Verify branch, PR, tree, and workflow references after every write
Later commit SHAs were mentioned in replies but did not match the live branch/PR head during the
retrospective. This is a process-integrity issue. Confirm the write SHA, branch ref, PR head, changed
file tree, and workflow run SHA before saying “pushed” or “verified.” If they disagree, reconcile them.

### 9. Keep the docs aligned with code
Phase II has a stale checklist and Phase III PR text has not fully caught up with the initial ledger
work. Update status and remaining tasks in the same change as a substantive implementation; stale
docs can mislead future debugging.

### 10. Progress percentages need acceptance criteria
The dialogue used 45%, 50%, 55%, 58%, 60%, and 62% estimates without a formal weighted rubric, and
some increases preceded CI validation. Preserve those figures as chat history only. Going forward,
each increase should be tied to an explicit milestone, tests, exact SHA, and recorded CI result.
Formatting-only or unverified code is not an appropriate reason to increase progress.

### 11. Make engineering records explanatory
A useful log is not merely a list of commit messages. It explains why a change was needed, why the fix
addresses the failure, what evidence proves it, what remains unknown, and which lesson should affect
future work.

### 12. Record failed attempts honestly
When a correction still fails, document that outcome and the new evidence. Don't declare a suspected
fix complete before the tested SHA passes the relevant gate. Failed attempts are useful when they
expose hidden assumptions or improve the workflow.

## Future development loop

1. Read the live branch and PR head.
2. Inspect CI failure output or define one substantial acceptance milestone.
3. Make a coherent code + tests + docs change.
4. Run local checks if available; otherwise treat CI as the validator.
5. Commit implementation and the corresponding log entry together.
6. Verify branch SHA, PR head SHA, tree contents, and CI SHA agree.
7. Read actual step results, not only the overall status.
8. Update progress only when a milestone is supported by implementation and verification evidence.
