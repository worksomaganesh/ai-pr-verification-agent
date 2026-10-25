# Phase III — CI/CD run-by-run audit

Snapshot source: GitHub Actions API (284 repository runs scanned, three pages). Filtered to `phase-3-evidence-ingestion` and `phase-3-trust-bootstrap`: **120 runs** (115 implementation; 5 bootstrap). Outcomes: 8 success, 104 failure, 8 cancelled.

Each run record below includes run ID, number, SHA, branch, event, dates, result, and the verified lesson. A failure cause is not inferred from the conclusion alone; detailed logs are linked where a known failure was inspected.

## Run #162 — 39105498466

- **Run:** [GitHub Actions #39105498466](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39105498466)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `eb207edc8a4e5eb60f33ed880e51160c6c5eeffe` — [commit record](commits.md#eb207ed)
- **Created / updated (UTC):** 2026-10-18T06:51:03Z / 2026-10-18T06:51:27Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** Strict mypy failed after formatter and Ruff passed: `tests/unit/test_phase_three_worker.py:311: Returning Any from function declared to return VerificationObligation [no-any-return]`. Unit/property tests and coverage gates were skipped; the authenticated evidence artifact job was also skipped. The reconciliation fake in the new test needs an explicit non-Any return/concrete obligation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #163 — 39113225504

- **Run:** [GitHub Actions #39113225504](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39113225504)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `48279e4714742a7e39a482a51a5692c59d7fc589` — [commit record](commits.md#48279e4)
- **Created / updated (UTC):** 2026-10-18T08:53:58Z / 2026-10-18T08:54:22Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #164 — 39113783236

- **Run:** [GitHub Actions #39113783236](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39113783236)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `a96c2cdff4a990b64a80f27438d0aadfe0ab460a` — [commit record](commits.md#a96c2cd)
- **Created / updated (UTC):** 2026-10-18T09:02:37Z / 2026-10-18T09:03:00Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #165 — 39113824052

- **Run:** [GitHub Actions #39113824052](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39113824052)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `9624f122bb3abe507fb0f51b1fcdfc6d0e6bf74b` — [commit record](commits.md#9624f12)
- **Created / updated (UTC):** 2026-10-18T09:03:15Z / 2026-10-18T09:03:45Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #166 — 39113850235

- **Run:** [GitHub Actions #39113850235](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39113850235)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `ef86d2de4632aa49340f87b453868edde8c44800` — [commit record](commits.md#ef86d2d)
- **Created / updated (UTC):** 2026-10-18T09:03:38Z / 2026-10-18T09:04:11Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #167 — 39114134975

- **Run:** [GitHub Actions #39114134975](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114134975)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `625794d274ae38d022b663d256cd761d8ae4eca7` — [commit record](commits.md#625794d)
- **Created / updated (UTC):** 2026-10-18T09:08:01Z / 2026-10-18T09:08:25Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #168 — 39114358595

- **Run:** [GitHub Actions #39114358595](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114358595)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `f07275224b3741c83559363ffa681c949e21a110` — [commit record](commits.md#f072752)
- **Created / updated (UTC):** 2026-10-18T09:11:29Z / 2026-10-18T09:11:54Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #169 — 39114474362

- **Run:** [GitHub Actions #39114474362](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114474362)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `231cb167f889b92eaa8de89282e51abc3c5e0851` — [commit record](commits.md#231cb16)
- **Created / updated (UTC):** 2026-10-18T09:13:16Z / 2026-10-18T09:13:41Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #170 — 39114713879

- **Run:** [GitHub Actions #39114713879](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114713879)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `5bdb24ba41de8b143cd2c05d29b471281ad18aad` — [commit record](commits.md#5bdb24b)
- **Created / updated (UTC):** 2026-10-18T09:16:55Z / 2026-10-18T09:17:14Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #171 — 39114790323

- **Run:** [GitHub Actions #39114790323](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114790323)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `0aa8739d6d0d7c10866f2d702c58c76e8ea7f6d4` — [commit record](commits.md#0aa8739)
- **Created / updated (UTC):** 2026-10-18T09:18:06Z / 2026-10-18T09:18:24Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #172 — 39114844452

- **Run:** [GitHub Actions #39114844452](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114844452)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `832d704d999767ff1e5662a7a080fd38236921ce` — [commit record](commits.md#832d704)
- **Created / updated (UTC):** 2026-10-18T09:18:56Z / 2026-10-18T09:19:19Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #173 — 39114872888

- **Run:** [GitHub Actions #39114872888](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114872888)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `0ffd98fa2361fcd679f5dc591f692d33e9fe67fa` — [commit record](commits.md#0ffd98f)
- **Created / updated (UTC):** 2026-10-18T09:19:24Z / 2026-10-18T09:19:54Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #174 — 39114906563

- **Run:** [GitHub Actions #39114906563](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114906563)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `65004812e07816f439e767f2e4dd100cee69400b` — [commit record](commits.md#6500481)
- **Created / updated (UTC):** 2026-10-18T09:19:56Z / 2026-10-18T09:20:20Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #175 — 39114943822

- **Run:** [GitHub Actions #39114943822](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39114943822)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `7feb24ecbb284f0712077589f4cbdc7426868851` — [commit record](commits.md#7feb24e)
- **Created / updated (UTC):** 2026-10-18T09:20:28Z / 2026-10-18T09:20:52Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #176 — 39116175331

- **Run:** [GitHub Actions #39116175331](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39116175331)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `ec002cc96859225599eea2d5223c9b30bfb8eed2` — [commit record](commits.md#ec002cc)
- **Created / updated (UTC):** 2026-10-18T09:39:10Z / 2026-10-18T09:39:28Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #177 — 39116205421

- **Run:** [GitHub Actions #39116205421](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39116205421)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `6790d4f97e1f6bd8a7e9be63f538d6d0ad68e86d` — [commit record](commits.md#6790d4f)
- **Created / updated (UTC):** 2026-10-18T09:39:37Z / 2026-10-18T09:39:55Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #178 — 39116236583

- **Run:** [GitHub Actions #39116236583](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39116236583)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `36fd1553ec7495e3290c50d44e8700f0a6768bd2` — [commit record](commits.md#36fd155)
- **Created / updated (UTC):** 2026-10-18T09:40:06Z / 2026-10-18T09:40:30Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #179 — 39118161485

- **Run:** [GitHub Actions #39118161485](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39118161485)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `d3a934857a98fb7e705f4bee0d1f39af6a315d9f` — [commit record](commits.md#d3a9348)
- **Created / updated (UTC):** 2026-10-18T10:09:50Z / 2026-10-18T10:10:20Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #180 — 39118646854

- **Run:** [GitHub Actions #39118646854](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39118646854)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `388aa5c103f770ea38cc82224eac97adcaeaa712` — [commit record](commits.md#388aa5c)
- **Created / updated (UTC):** 2026-10-18T10:17:15Z / 2026-10-18T10:17:42Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #181 — 39121200907

- **Run:** [GitHub Actions #39121200907](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39121200907)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `1618fd6d6b9eb3964ba664966f2e7a4ac3ccffb5` — [commit record](commits.md#1618fd6)
- **Created / updated (UTC):** 2026-10-18T10:56:07Z / 2026-10-18T10:56:30Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #182 — 39121255357

- **Run:** [GitHub Actions #39121255357](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39121255357)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `5ce5c45b2502a6d7ecf45c9fda4285f0bf124002` — [commit record](commits.md#5ce5c45)
- **Created / updated (UTC):** 2026-10-18T10:56:56Z / 2026-10-18T10:57:20Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #183 — 39121411287

- **Run:** [GitHub Actions #39121411287](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39121411287)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `1d90810c75ead4feef95857e605aae1568e94d08` — [commit record](commits.md#1d90810)
- **Created / updated (UTC):** 2026-10-18T10:59:26Z / 2026-10-18T10:59:46Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #184 — 39121584986

- **Run:** [GitHub Actions #39121584986](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39121584986)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `18f3baa4f134e1c51c6487518326be5d7fea48d3` — [commit record](commits.md#18f3baa)
- **Created / updated (UTC):** 2026-10-18T11:01:51Z / 2026-10-18T11:02:14Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #185 — 39121896726

- **Run:** [GitHub Actions #39121896726](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39121896726)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `0933e421a2b2cc3a87a4c92e1b6a32c62892c797` — [commit record](commits.md#0933e42)
- **Created / updated (UTC):** 2026-10-18T11:06:26Z / 2026-10-18T11:06:59Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #186 — 39121925826

- **Run:** [GitHub Actions #39121925826](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39121925826)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `a4a1d1586c3a1a29feafddc3421d4f281f03a887` — [commit record](commits.md#a4a1d15)
- **Created / updated (UTC):** 2026-10-18T11:06:50Z / 2026-10-18T11:07:26Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #187 — 39122152558

- **Run:** [GitHub Actions #39122152558](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39122152558)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `d71b966d63352cecb5174df3d254bcc8143e04c6` — [commit record](commits.md#d71b966)
- **Created / updated (UTC):** 2026-10-18T11:10:17Z / 2026-10-18T11:10:45Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #188 — 39126961351

- **Run:** [GitHub Actions #39126961351](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39126961351)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `e33236e36c4c1b2b98c8a227a4d045528d0c257b` — [commit record](commits.md#e33236e)
- **Created / updated (UTC):** 2026-10-18T12:21:46Z / 2026-10-18T12:22:11Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #189 — 39127365132

- **Run:** [GitHub Actions #39127365132](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39127365132)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `c25188d4dc3fad286e9df753dde271e67eb5e997` — [commit record](commits.md#c25188d)
- **Created / updated (UTC):** 2026-10-18T12:27:40Z / 2026-10-18T12:28:06Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #190 — 39127801970

- **Run:** [GitHub Actions #39127801970](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39127801970)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `a9916adecd2b93915ccb9c7e6c3c01966ca95c2c` — [commit record](commits.md#a9916ad)
- **Created / updated (UTC):** 2026-10-18T12:33:51Z / 2026-10-18T12:34:14Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #191 — 39128785726

- **Run:** [GitHub Actions #39128785726](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39128785726)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `c1acc4e7417f88b0e15a777efff8e4c2d24369a0` — [commit record](commits.md#c1acc4e)
- **Created / updated (UTC):** 2026-10-18T12:47:49Z / 2026-10-18T12:48:09Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #192 — 39129212422

- **Run:** [GitHub Actions #39129212422](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39129212422)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `ce0f767698428aa78138891ce529c87c8ed9ed6d` — [commit record](commits.md#ce0f767)
- **Created / updated (UTC):** 2026-10-18T12:53:55Z / 2026-10-18T12:54:19Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #193 — 39129403271

- **Run:** [GitHub Actions #39129403271](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39129403271)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `4bc64238dc2faab20cf4d4a6db07d4da3489c8f6` — [commit record](commits.md#4bc6423)
- **Created / updated (UTC):** 2026-10-18T12:56:40Z / 2026-10-18T12:57:01Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #194 — 39129484914

- **Run:** [GitHub Actions #39129484914](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39129484914)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `19ebc5be866adfbe9f0993a3dd62a1f2db146cdf` — [commit record](commits.md#19ebc5b)
- **Created / updated (UTC):** 2026-10-18T12:57:54Z / 2026-10-18T12:58:21Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #196 — 39132715519

- **Run:** [GitHub Actions #39132715519](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39132715519)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `b8f4c6cad122396807701d1cb279a0f91f0c7cb9` — [commit record](commits.md#b8f4c6c)
- **Created / updated (UTC):** 2026-10-18T13:42:21Z / 2026-10-18T13:42:44Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #197 — 39143573401

- **Run:** [GitHub Actions #39143573401](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39143573401)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `2797782c0ad9b55f3cca5ddb8e63b2f3bce12879` — [commit record](commits.md#2797782)
- **Created / updated (UTC):** 2026-10-18T16:07:28Z / 2026-10-18T16:07:53Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #198 — 39143710693

- **Run:** [GitHub Actions #39143710693](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39143710693)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `49b08d912ea99ef3884488e84a0c17d0880d24a7` — [commit record](commits.md#49b08d9)
- **Created / updated (UTC):** 2026-10-18T16:09:18Z / 2026-10-18T16:09:57Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #199 — 39143886828

- **Run:** [GitHub Actions #39143886828](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39143886828)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `cd94f919fda29e0709236db9537f54dd75acbc56` — [commit record](commits.md#cd94f91)
- **Created / updated (UTC):** 2026-10-18T16:11:38Z / 2026-10-18T16:12:03Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #200 — 39143973263

- **Run:** [GitHub Actions #39143973263](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39143973263)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `db2cb27b5d23187cd8f4917b41303a8a2b84183a` — [commit record](commits.md#db2cb27)
- **Created / updated (UTC):** 2026-10-18T16:12:48Z / 2026-10-18T16:14:02Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #201 — 39144197581

- **Run:** [GitHub Actions #39144197581](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39144197581)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `54acdb059c5665a74204877f206d6e38c39cb562` — [commit record](commits.md#54acdb0)
- **Created / updated (UTC):** 2026-10-18T16:15:45Z / 2026-10-18T16:16:07Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #202 — 39144294366

- **Run:** [GitHub Actions #39144294366](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39144294366)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `f7f1ca22f6c29eac52506eea71028c271150663a` — [commit record](commits.md#f7f1ca2)
- **Created / updated (UTC):** 2026-10-18T16:17:04Z / 2026-10-18T16:17:27Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #203 — 39144389166

- **Run:** [GitHub Actions #39144389166](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39144389166)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `54498841ad391442f6746cd4e0cc52a6aaf0c1e6` — [commit record](commits.md#5449884)
- **Created / updated (UTC):** 2026-10-18T16:18:20Z / 2026-10-18T16:19:07Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #204 — 39144723077

- **Run:** [GitHub Actions #39144723077](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39144723077)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `c43624460d6996546b15aadcf44190491b415ab8` — [commit record](commits.md#c436244)
- **Created / updated (UTC):** 2026-10-18T16:22:46Z / 2026-10-18T16:23:09Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #205 — 39144827719

- **Run:** [GitHub Actions #39144827719](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39144827719)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `55048e50a9cec7717087b0d68c605b08d179b689` — [commit record](commits.md#55048e5)
- **Created / updated (UTC):** 2026-10-18T16:24:08Z / 2026-10-18T16:24:32Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #206 — 39144951098

- **Run:** [GitHub Actions #39144951098](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39144951098)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `4a4e91280cef83c1bf16a1d19f46f1c5acef9d89` — [commit record](commits.md#4a4e912)
- **Created / updated (UTC):** 2026-10-18T16:25:46Z / 2026-10-18T16:26:13Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #207 — 39145069685

- **Run:** [GitHub Actions #39145069685](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39145069685)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `ba275e727435509e69ad317331a23d73b73fe972` — [commit record](commits.md#ba275e7)
- **Created / updated (UTC):** 2026-10-18T16:27:22Z / 2026-10-18T16:27:47Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #208 — 39145161595

- **Run:** [GitHub Actions #39145161595](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39145161595)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `88a0039c659a18534720eba3b1d4a042a9a5f021` — [commit record](commits.md#88a0039)
- **Created / updated (UTC):** 2026-10-18T16:28:36Z / 2026-10-18T16:28:58Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #209 — 39145290937

- **Run:** [GitHub Actions #39145290937](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39145290937)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `34df9e9c9aaf8f58bdd62a0a2070169da563a4df` — [commit record](commits.md#34df9e9)
- **Created / updated (UTC):** 2026-10-18T16:30:16Z / 2026-10-18T16:30:49Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #210 — 39146736581

- **Run:** [GitHub Actions #39146736581](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39146736581)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `699b7cda35b02d73b31ee0f15298963230100a63` — [commit record](commits.md#699b7cd)
- **Created / updated (UTC):** 2026-10-18T16:49:10Z / 2026-10-18T16:50:18Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #211 — 39147326269

- **Run:** [GitHub Actions #39147326269](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39147326269)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `2a86a1e8c77b0295789e13cf71c03e0f217ae4ed` — [commit record](commits.md#2a86a1e)
- **Created / updated (UTC):** 2026-10-18T16:57:02Z / 2026-10-18T16:57:28Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #212 — 39147354586

- **Run:** [GitHub Actions #39147354586](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39147354586)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `d2a1e0c2a08e3a702ff9814eee408b3606e4ea37` — [commit record](commits.md#d2a1e0c)
- **Created / updated (UTC):** 2026-10-18T16:57:27Z / 2026-10-18T16:57:51Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #213 — 39149971965

- **Run:** [GitHub Actions #39149971965](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39149971965)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `a2e4b5a49717b350a59d980bc659aea86a47adac` — [commit record](commits.md#a2e4b5a)
- **Created / updated (UTC):** 2026-10-18T17:31:22Z / 2026-10-18T17:31:49Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #214 — 39168603830

- **Run:** [GitHub Actions #39168603830](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39168603830)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `f2e42135d99fb54ae13d2a74c9ecd77ce4b7739c` — [commit record](commits.md#f2e4213)
- **Created / updated (UTC):** 2026-10-18T21:36:42Z / 2026-10-18T21:37:10Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #215 — 39168709842

- **Run:** [GitHub Actions #39168709842](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39168709842)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `e6723d4bf20f2add9899b2a3dff922569530711b` — [commit record](commits.md#e6723d4)
- **Created / updated (UTC):** 2026-10-18T21:38:09Z / 2026-10-18T21:38:38Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #216 — 39168907861

- **Run:** [GitHub Actions #39168907861](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39168907861)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `208c32f8b24f8c7b027bf04f7203a49d2bc3ee02` — [commit record](commits.md#208c32f)
- **Created / updated (UTC):** 2026-10-18T21:40:52Z / 2026-10-18T21:41:16Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #217 — 39169027616

- **Run:** [GitHub Actions #39169027616](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169027616)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `d2608e884a8687598f0c60ac31c475615619b403` — [commit record](commits.md#d2608e8)
- **Created / updated (UTC):** 2026-10-18T21:42:29Z / 2026-10-18T21:42:56Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #218 — 39169167290

- **Run:** [GitHub Actions #39169167290](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169167290)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `324b0e2b3c9f8d56d36575478a22a9b6298ec1c5` — [commit record](commits.md#324b0e2)
- **Created / updated (UTC):** 2026-10-18T21:44:28Z / 2026-10-18T21:44:55Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #219 — 39169277725

- **Run:** [GitHub Actions #39169277725](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169277725)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `4cd59b8c306626f96629749390c43078f2f7b222` — [commit record](commits.md#4cd59b8)
- **Created / updated (UTC):** 2026-10-18T21:46:02Z / 2026-10-18T21:46:54Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #220 — 39169489142

- **Run:** [GitHub Actions #39169489142](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169489142)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `be2b0079c15c984f6342d75ba11b30eb4210c2be` — [commit record](commits.md#be2b007)
- **Created / updated (UTC):** 2026-10-18T21:48:57Z / 2026-10-18T21:49:16Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #221 — 39169566240

- **Run:** [GitHub Actions #39169566240](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169566240)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `8ff372537b6026e14b3f6492288aa727d4259e14` — [commit record](commits.md#8ff3725)
- **Created / updated (UTC):** 2026-10-18T21:50:03Z / 2026-10-18T21:50:25Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #222 — 39169688736

- **Run:** [GitHub Actions #39169688736](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169688736)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `4f6694c770f6be3d4945257904d55970158a4e91` — [commit record](commits.md#4f6694c)
- **Created / updated (UTC):** 2026-10-18T21:51:43Z / 2026-10-18T21:52:52Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #223 — 39169948086

- **Run:** [GitHub Actions #39169948086](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169948086)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `b50b15269a34a1803a7fb1210d74ceb4d33c5fb3` — [commit record](commits.md#b50b152)
- **Created / updated (UTC):** 2026-10-18T21:55:19Z / 2026-10-18T21:55:47Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #224 — 39170044123

- **Run:** [GitHub Actions #39170044123](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39170044123)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `79dfedb44cd7cb9de8f6b51dc53d967074b83c91` — [commit record](commits.md#79dfedb)
- **Created / updated (UTC):** 2026-10-18T21:56:41Z / 2026-10-18T21:57:03Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #225 — 39170153927

- **Run:** [GitHub Actions #39170153927](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39170153927)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `c93088b571b661ff949de0cc24b8e0259d7e8d1f` — [commit record](commits.md#c93088b)
- **Created / updated (UTC):** 2026-10-18T21:58:14Z / 2026-10-18T21:58:33Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #226 — 39170237791

- **Run:** [GitHub Actions #39170237791](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39170237791)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `e10cebde7af412e074a847420215c19c2ab9c039` — [commit record](commits.md#e10cebd)
- **Created / updated (UTC):** 2026-10-18T21:59:28Z / 2026-10-18T22:00:43Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #227 — 39171029125

- **Run:** [GitHub Actions #39171029125](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39171029125)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `b4e43eb0111e80be060d7665e403b0fccd223f1c` — [commit record](commits.md#b4e43eb)
- **Created / updated (UTC):** 2026-10-18T22:10:00Z / 2026-10-18T22:10:29Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #228 — 39193333525

- **Run:** [GitHub Actions #39193333525](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39193333525)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `9384490a5697e4f9144242d755efc3373ba16396` — [commit record](commits.md#9384490)
- **Created / updated (UTC):** 2026-10-19T03:09:30Z / 2026-10-19T03:10:44Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #229 — 39194526404

- **Run:** [GitHub Actions #39194526404](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194526404)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `9b42aba85e0979af86ac704f4cb5926f298859bf` — [commit record](commits.md#9b42aba)
- **Created / updated (UTC):** 2026-10-19T03:24:18Z / 2026-10-19T03:24:43Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #230 — 39194649771

- **Run:** [GitHub Actions #39194649771](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194649771)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `6fd170f0bd7cd521d46a59f034f988106c8cea25` — [commit record](commits.md#6fd170f)
- **Created / updated (UTC):** 2026-10-19T03:25:51Z / 2026-10-19T03:26:18Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #231 — 39194755446

- **Run:** [GitHub Actions #39194755446](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194755446)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `78def233a8ebe20fd20132fe178de5a1d9b6d683` — [commit record](commits.md#78def23)
- **Created / updated (UTC):** 2026-10-19T03:27:13Z / 2026-10-19T03:27:38Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #232 — 39194881289

- **Run:** [GitHub Actions #39194881289](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194881289)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `e7019d324d39da1d7ab477362470e8a3308421d4` — [commit record](commits.md#e7019d3)
- **Created / updated (UTC):** 2026-10-19T03:28:51Z / 2026-10-19T03:29:16Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #233 — 39195030380

- **Run:** [GitHub Actions #39195030380](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195030380)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `66a840f9ee7e01457f28e12d495cc8aaaf376064` — [commit record](commits.md#66a840f)
- **Created / updated (UTC):** 2026-10-19T03:30:41Z / 2026-10-19T03:31:50Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #234 — 39195221364

- **Run:** [GitHub Actions #39195221364](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195221364)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `172abf66dc2378d26ae6b4a19c5c35111fb7ad94` — [commit record](commits.md#172abf6)
- **Created / updated (UTC):** 2026-10-19T03:33:10Z / 2026-10-19T03:35:26Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #235 — 39195545167

- **Run:** [GitHub Actions #39195545167](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195545167)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `9e47e64764418be1d23caea8983f162b29c2cbe3` — [commit record](commits.md#9e47e64)
- **Created / updated (UTC):** 2026-10-19T03:37:11Z / 2026-10-19T03:37:43Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #236 — 39195904599

- **Run:** [GitHub Actions #39195904599](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195904599)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `e6ed8a9d0613028cf96f17ada0f8cb8d41e8292c` — [commit record](commits.md#e6ed8a9)
- **Created / updated (UTC):** 2026-10-19T03:41:46Z / 2026-10-19T03:43:35Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #237 — 39196884255

- **Run:** [GitHub Actions #39196884255](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39196884255)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `ad15bb9e393dbe0192f96b37f88d0ad41fa939cf` — [commit record](commits.md#ad15bb9)
- **Created / updated (UTC):** 2026-10-19T03:54:28Z / 2026-10-19T03:56:33Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #238 — 39197428272

- **Run:** [GitHub Actions #39197428272](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39197428272)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `44d89d9aaa19595736d671eae8b8b97762e9e9f6` — [commit record](commits.md#44d89d9)
- **Created / updated (UTC):** 2026-10-19T04:01:27Z / 2026-10-19T04:03:39Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #239 — 39197824251

- **Run:** [GitHub Actions #39197824251](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39197824251)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `7cde403a0c6fdf72a1e2d89e62265f1f8fa95b94` — [commit record](commits.md#7cde403)
- **Created / updated (UTC):** 2026-10-19T04:06:28Z / 2026-10-19T04:08:41Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #240 — 39219163228

- **Run:** [GitHub Actions #39219163228](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39219163228)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `17d0e26066f35fe83412259f364ec814255ffd1b` — [commit record](commits.md#17d0e26)
- **Created / updated (UTC):** 2026-10-19T07:55:33Z / 2026-10-19T07:56:01Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #241 — 39219463813

- **Run:** [GitHub Actions #39219463813](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39219463813)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `2039ec4b7e0cc211a13baf8a2340e2e31aa94080` — [commit record](commits.md#2039ec4)
- **Created / updated (UTC):** 2026-10-19T07:58:13Z / 2026-10-19T07:58:31Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #242 — 39219692769

- **Run:** [GitHub Actions #39219692769](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39219692769)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `131240d55dd90dbcaea697b5e83bbc49391eb998` — [commit record](commits.md#131240d)
- **Created / updated (UTC):** 2026-10-19T08:00:18Z / 2026-10-19T08:02:19Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #243 — 39220114379

- **Run:** [GitHub Actions #39220114379](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39220114379)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `9c9b78ffd87b3d21d27674e1dd45445f488ae4e6` — [commit record](commits.md#9c9b78f)
- **Created / updated (UTC):** 2026-10-19T08:03:53Z / 2026-10-19T08:05:39Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #244 — 39223871999

- **Run:** [GitHub Actions #39223871999](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39223871999)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `ec58893ce2490a8fac98ece9cbbed1ea7ebe6640` — [commit record](commits.md#ec58893)
- **Created / updated (UTC):** 2026-10-19T08:35:37Z / 2026-10-19T08:36:08Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #245 — 39224141676

- **Run:** [GitHub Actions #39224141676](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39224141676)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `26f2d197396cbed74d5232a6b0c66b992a9912ab` — [commit record](commits.md#26f2d19)
- **Created / updated (UTC):** 2026-10-19T08:37:53Z / 2026-10-19T08:39:35Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #246 — 39812879743

- **Run:** [GitHub Actions #39812879743](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39812879743)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `e0775ef03300c8ff915c0c13a23ab9954af66006` — [commit record](commits.md#e0775ef)
- **Created / updated (UTC):** 2026-10-22T16:18:18Z / 2026-10-22T16:20:16Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #247 — 39813965772

- **Run:** [GitHub Actions #39813965772](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39813965772)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `6485f828f6116c68593fea2870976106cd74b240` — [commit record](commits.md#6485f82)
- **Created / updated (UTC):** 2026-10-22T16:25:38Z / 2026-10-22T16:26:07Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #248 — 39814823241

- **Run:** [GitHub Actions #39814823241](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39814823241)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `f721d73dea35a04889878b776b7e87f61ae0206c` — [commit record](commits.md#f721d73)
- **Created / updated (UTC):** 2026-10-22T16:31:45Z / 2026-10-22T16:41:26Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #249 — 39815565602

- **Run:** [GitHub Actions #39815565602](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39815565602)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `d5540a19a17c50b9dd7457ecfa4340afdd1d2365` — [commit record](commits.md#d5540a1)
- **Created / updated (UTC):** 2026-10-22T16:37:46Z / 2026-10-22T16:43:06Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #250 — 39817064462

- **Run:** [GitHub Actions #39817064462](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39817064462)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `c2b5aba35de713dc7d3585518f0e0e9f8b70e0e6` — [commit record](commits.md#c2b5aba)
- **Created / updated (UTC):** 2026-10-22T16:48:16Z / 2026-10-22T16:48:56Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #251 — 39817505536

- **Run:** [GitHub Actions #39817505536](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39817505536)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `e6b394ea9f598a7a12d4b98728eeb94d6f4cdc32` — [commit record](commits.md#e6b394e)
- **Created / updated (UTC):** 2026-10-22T16:51:03Z / 2026-10-22T16:53:00Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #252 — 39893897122

- **Run:** [GitHub Actions #39893897122](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39893897122)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `671198acf5cb082532b74b297a29f84f32ddad17` — [commit record](commits.md#671198a)
- **Created / updated (UTC):** 2026-10-23T03:13:58Z / 2026-10-23T03:14:21Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #253 — 39894007001

- **Run:** [GitHub Actions #39894007001](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39894007001)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `1fa989731b39cbfccb5296d8f270caec786bf1db` — [commit record](commits.md#1fa9897)
- **Created / updated (UTC):** 2026-10-23T03:15:10Z / 2026-10-23T03:15:42Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #254 — 39894146843

- **Run:** [GitHub Actions #39894146843](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39894146843)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `8749b46c762ad63fb732eed663089634b73669cb` — [commit record](commits.md#8749b46)
- **Created / updated (UTC):** 2026-10-23T03:16:43Z / 2026-10-23T03:17:09Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #255 — 39894345129

- **Run:** [GitHub Actions #39894345129](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39894345129)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `58eb5b21acee4fd20144c70d4bb2157a7759928b` — [commit record](commits.md#58eb5b2)
- **Created / updated (UTC):** 2026-10-23T03:18:56Z / 2026-10-23T03:19:24Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #256 — 39902193903

- **Run:** [GitHub Actions #39902193903](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39902193903)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `fe017303a24ba3a774f2632cb8d2435bc5dcea9e` — [commit record](commits.md#fe01730)
- **Created / updated (UTC):** 2026-10-23T04:47:24Z / 2026-10-23T04:47:48Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #257 — 39902316322

- **Run:** [GitHub Actions #39902316322](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39902316322)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `591d21892bf690875e59dc068e0d82453187f8b4` — [commit record](commits.md#591d218)
- **Created / updated (UTC):** 2026-10-23T04:48:46Z / 2026-10-23T04:49:13Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #258 — 39902428152

- **Run:** [GitHub Actions #39902428152](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39902428152)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `23320b975968c5499b6418db8f249844c10bc841` — [commit record](commits.md#23320b9)
- **Created / updated (UTC):** 2026-10-23T04:50:03Z / 2026-10-23T04:50:31Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #259 — 39907385124

- **Run:** [GitHub Actions #39907385124](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907385124)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `0a4e8ee419859d79367a5100ab31b1bfbc66337b` — [commit record](commits.md#0a4e8ee)
- **Created / updated (UTC):** 2026-10-23T05:43:56Z / 2026-10-23T05:45:07Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #260 — 39907824858

- **Run:** [GitHub Actions #39907824858](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907824858)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `ce5f0c5b70112bc4885aaf5c4a2442637345deaa` — [commit record](commits.md#ce5f0c5)
- **Created / updated (UTC):** 2026-10-23T05:48:41Z / 2026-10-23T05:49:06Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #262 — 40187204525

- **Run:** [GitHub Actions #40187204525](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40187204525)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-trust-bootstrap` / `pull_request`
- **Head SHA:** `cc4f7f5724146c298e4cd2582e12460699a65e30`
- **Created / updated (UTC):** 2026-10-25T11:02:21Z / 2026-10-25T11:04:13Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #263 — 40187464587

- **Run:** [GitHub Actions #40187464587](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40187464587)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-trust-bootstrap` / `pull_request`
- **Head SHA:** `3e3dd8de98bf1ab79b0d6cbf50eaf8689e9847bc`
- **Created / updated (UTC):** 2026-10-25T11:06:10Z / 2026-10-25T11:06:51Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #264 — 40187561638

- **Run:** [GitHub Actions #40187561638](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40187561638)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-trust-bootstrap` / `pull_request`
- **Head SHA:** `42a9271a494141616818dcea33890b0b26f9a06d`
- **Created / updated (UTC):** 2026-10-25T11:07:37Z / 2026-10-25T11:09:48Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #265 — 40187985188

- **Run:** [GitHub Actions #40187985188](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40187985188)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-trust-bootstrap` / `pull_request`
- **Head SHA:** `2d98b53947aa029c7fa3a14b94c0276f79f095e6`
- **Created / updated (UTC):** 2026-10-25T11:13:51Z / 2026-10-25T11:16:03Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #266 — 40188223783

- **Run:** [GitHub Actions #40188223783](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40188223783)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-trust-bootstrap` / `pull_request`
- **Head SHA:** `3383880b381b323ff8b09b18be30d4aa58f8764d`
- **Created / updated (UTC):** 2026-10-25T11:17:13Z / 2026-10-25T11:19:27Z
- **Status / conclusion:** `completed` / `success`
- **What happened:** success.
- **Why tracker did not move:** This run passed for this SHA and its configured job set only; later commits need their own validation.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Check artifact list and producer identity, then validate the latest commit SHA.

## Run #268 — 40188929251

- **Run:** [GitHub Actions #40188929251](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40188929251)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `37e714385d888e0c63e810d0447f0824b18c10a3` — [commit record](commits.md#37e7143)
- **Created / updated (UTC):** 2026-10-25T11:27:19Z / 2026-10-25T11:27:44Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #269 — 40188983461

- **Run:** [GitHub Actions #40188983461](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40188983461)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `90ce6d7d74ceb88990b670a4c773fd9fee0c3d12` — [commit record](commits.md#90ce6d7)
- **Created / updated (UTC):** 2026-10-25T11:28:07Z / 2026-10-25T11:28:14Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #270 — 40188988778

- **Run:** [GitHub Actions #40188988778](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40188988778)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `a3d09f96d6c85dbdcadd91b51548787cb612423e` — [commit record](commits.md#a3d09f9)
- **Created / updated (UTC):** 2026-10-25T11:28:11Z / 2026-10-25T11:28:48Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #271 — 40189071961

- **Run:** [GitHub Actions #40189071961](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189071961)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `1b4d8c8c609f49db7a7a5366aabee55c3321fd32` — [commit record](commits.md#1b4d8c8)
- **Created / updated (UTC):** 2026-10-25T11:29:24Z / 2026-10-25T11:29:32Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #272 — 40189077163

- **Run:** [GitHub Actions #40189077163](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189077163)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `853de84f10ee031b396c36ce3305b69cac0d59b6` — [commit record](commits.md#853de84)
- **Created / updated (UTC):** 2026-10-25T11:29:29Z / 2026-10-25T11:29:57Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #273 — 40189193556

- **Run:** [GitHub Actions #40189193556](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189193556)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `c3d170bb3cc0606752c65d5f512af741d7521227` — [commit record](commits.md#c3d170b)
- **Created / updated (UTC):** 2026-10-25T11:30:59Z / 2026-10-25T11:31:30Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #274 — 40189200153

- **Run:** [GitHub Actions #40189200153](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189200153)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `7f08de6b4b08a08a9e7931b580015cc39318de5c` — [commit record](commits.md#7f08de6)
- **Created / updated (UTC):** 2026-10-25T11:31:05Z / 2026-10-25T11:31:51Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #275 — 40189239988

- **Run:** [GitHub Actions #40189239988](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189239988)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `62fc8c158cb697a6bd05adabccf0def9450e2b80` — [commit record](commits.md#62fc8c1)
- **Created / updated (UTC):** 2026-10-25T11:31:41Z / 2026-10-25T11:31:49Z
- **Status / conclusion:** `completed` / `cancelled`
- **What happened:** cancelled.
- **Why tracker did not move:** Cancelled runs provide no complete acceptance evidence; rerun the current SHA.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Use a fresh run for the current SHA.

## Run #276 — 40189249042

- **Run:** [GitHub Actions #40189249042](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189249042)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `7ab9326896ec8316ead676bf27cffef8a9c19de8` — [commit record](commits.md#7ab9326)
- **Created / updated (UTC):** 2026-10-25T11:31:48Z / 2026-10-25T11:32:21Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #277 — 40189447960

- **Run:** [GitHub Actions #40189447960](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189447960)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `42f4dccb5ab33a101690c3a519091a3e2872beea` — [commit record](commits.md#42f4dcc)
- **Created / updated (UTC):** 2026-10-25T11:34:40Z / 2026-10-25T11:35:09Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #278 — 40189546516

- **Run:** [GitHub Actions #40189546516](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40189546516)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `3b8beaace5dd1a0f426a5869c7fac378526c2adb` — [commit record](commits.md#3b8beaa)
- **Created / updated (UTC):** 2026-10-25T11:36:03Z / 2026-10-25T11:36:29Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #279 — 40193833318

- **Run:** [GitHub Actions #40193833318](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40193833318)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `dfc3223e358e347f00c6001e28246f8a171f7ae4` — [commit record](commits.md#dfc3223)
- **Created / updated (UTC):** 2026-10-25T12:36:09Z / 2026-10-25T12:36:54Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #280 — 40194068208

- **Run:** [GitHub Actions #40194068208](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40194068208)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `8c071cc8e7ad88d453bff2314cd34387dda6cce3` — [commit record](commits.md#8c071cc)
- **Created / updated (UTC):** 2026-10-25T12:39:22Z / 2026-10-25T12:40:04Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #281 — 40194545728

- **Run:** [GitHub Actions #40194545728](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40194545728)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `066e554dac74577b89d597479648fcbb4be233e1` — [commit record](commits.md#066e554)
- **Created / updated (UTC):** 2026-10-25T12:45:36Z / 2026-10-25T12:45:58Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #282 — 40194646890

- **Run:** [GitHub Actions #40194646890](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40194646890)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `77561fdea2f70591398e037b1189febbb56be44f` — [commit record](commits.md#77561fd)
- **Created / updated (UTC):** 2026-10-25T12:46:59Z / 2026-10-25T12:47:28Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #283 — 40194926233

- **Run:** [GitHub Actions #40194926233](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40194926233)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `eeef80590d9730e00c7be66a17c670f239eb08a9` — [commit record](commits.md#eeef805)
- **Created / updated (UTC):** 2026-10-25T12:50:47Z / 2026-10-25T12:51:16Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.

## Run #284 — 40194994050

- **Run:** [GitHub Actions #40194994050](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40194994050)
- **Workflow:** Phase II CI (`.github/workflows/ci.yml`)
- **Branch/event:** `phase-3-evidence-ingestion` / `pull_request`
- **Head SHA:** `492c0cf8e32a95f8706d2f052dff7d504a809e62` — [commit record](commits.md#492c0cf)
- **Created / updated (UTC):** 2026-10-25T12:51:42Z / 2026-10-25T12:52:11Z
- **Status / conclusion:** `completed` / `failure`
- **What happened:** failure.
- **Why tracker did not move:** This run did not close release gates. Check the linked run’s first failing step; later steps may have been skipped.
- **Lesson:** Only exact-head, complete green gates with the required evidence artifact can count toward completion.
- **Next move:** Inspect the earliest failing job/step, fix the cause, and rerun without relaxing gates.
