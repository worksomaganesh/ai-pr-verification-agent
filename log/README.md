# Project Engineering Log

This directory is the durable engineering journal for **AI PR Verification Agent**. It documents what was built, why architectural choices were made, what failed, how failures were investigated, lessons learned, and what remains unverified. It covers the architecture phase through Phase I, Phase II, and the current Phase III effort.

A Git commit says what changed in a repository snapshot. This log explains the reasoning and evidence behind those changes.

## Index

- [Project history and phase timeline](project-history.md)
- [Phase I build history](phase-1-build-history.md)
- [Phase II build history](phase-2-build-history.md)
- [Phase III investigation log](phase-3-investigation.md)
- [Phase III progress, milestones, and CI evidence](phase-3-progress.md)
- [Engineering lessons learned](lessons-learned.md)
- [Current verified status](current-status.md)

## How this log is maintained

For each substantive milestone, record the context, code/test/documentation changes, failures or uncertainties, exact commit and CI evidence, lessons learned, and next acceptance criteria.

## Evidence rules

- A successful push is not proof that the code works.
- A green run on an older SHA does not verify a newer SHA.
- If CI stops at format or lint, later checks are **skipped**, not passed.
- The live GitHub branch ref, PR head, commit tree, and CI run SHA are authoritative. A hash mentioned in conversation is not considered delivered unless it is reachable from the intended branch or explicitly described as an unmerged attempt.
- Progress percentages are rough scope estimates, not test-pass ratios, coverage values, or release-readiness measures. Do not increase them for formatting-only or unverified changes.
- When an earlier statement proves inaccurate, correct it explicitly rather than silently rewriting the story.

This directory is being added directly to `main` as a project-wide retrospective. Phase III implementation remains on its separate draft PR until its release gates are satisfied.
