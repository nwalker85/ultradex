# Milestone M1 Review & Adversarial Challenge Report

## Review Summary

**Verdict**: APPROVE  
**Overall Risk Assessment**: LOW  
**Integrity Audit**: PASSED (Zero integrity violations; genuine implementation, deterministic scoring, rigorous test suites, and independent verification)

---

## 1. Observation

Direct observations from inspection of codebase and independent command executions:

### 1.1 Source & Test Artifacts
- **`core/jobsearch_profile.py`**:
  - Implements complete Pydantic v2 schemas: `SkillTier`, `SkillCategory`, `SkillItem` (aliased to `CandidateSkill`), `MLDepthSubdomain`, `ProductionMLDepth`, `WorkExperienceItem`, `EducationItem`, `ProjectHighlight`, `TargetRoleConfig`, `CompensationExpectations`, `CandidateBio`, and `CandidateProfile`.
  - Authoritative Profile seed data contains Nate Walker's complete resume narrative, 44 CTO skills partitioned strictly into 22 Expert and 22 Advanced across 7 categories, 6 Production ML depth pillars (LLM Orchestration, Voice ASR/TTS, Fine-Tuning, Hybrid RAG, Agent Loops/MCP, Hardware Inference), and compensation bounds ($180,000 USD base minimum / $250,000 USD target total comp / $200,000 USD minimum total comp).
  - `CandidateProfileStore` provides memory-cached profile retrieval, fallback persistence to `SettingsDB`, helper accessors, and deterministic regex token-based `match_skills(text)`.

- **`core/jobsearch_sourcing.py`**:
  - Implements `JobBoardId` enum, `CompensationRange`, `JobPosting` (aliased to `RawJobPosting`), `ProfileMatchScore` (aliased to `MatchBreakdown`), `ScoredJobLead`, and `JobSensingSummary`.
  - Implements 10 registered career board adapters (`LinkedInJobAdapter`, `AnthropicJobAdapter`, `OpenAIJobAdapter`, `ParloaJobAdapter`, `DeepgramJobAdapter`, `SoundHoundJobAdapter`, `LivePersonJobAdapter`, `ScaleAIJobAdapter`, `GoogleJobAdapter`, `AWSJobAdapter`) in `BOARD_REGISTRY`.
  - Deterministic 5-factor scoring engine `compute_profile_match`: Role Fit (25 pts), Skill Overlap (35 pts), Production ML Depth (20 pts), Compensation Fit (15 pts), Location Fit (5 pts).
  - Hard employer exclusion gate for former employers (`SoundHound AI`, `Amelia`, `IPsoft Amelia`, `Quant`, `IntelePeer`) immediately scoring 0 with `employer_excluded` risk flag.
  - `JobSourcingEngine` handles board querying, posting deduplication, lead scoring (`source_and_score_leads`), and summary statistics (`sense_jobs`).
  - `JobSweep` calculates canonical SHA-256 state commitments and declares stashes in `SweepStash`.

- **`cli/sense_jobs.py`**:
  - Full CLI runner with `--live`, `--mock`, `--board`, `--limit`, `--min-score`, `--dry-run`, `--json`, `--output`, and `--ingest` flags.
  - Formats ASCII tables and supports structured JSON emission.

- **`api/routes/profile.py` & `api/main.py`**:
  - FastAPI endpoints: `GET /profile`, `PUT /profile`, `GET /profile/skills`, `GET /profile/ml-depth`, `GET /profile/roles` (and mounted at both `/profile` and `/api/v1/profile`).

- **`tests/test_jobsearch_profile.py`**:
  - 53 test cases covering Tier 1 (Happy Path), Tier 2 (Boundary Value Analysis, negative compensation, text sanitization, irrelevant roles, employer exclusions), Tier 3 (10-case pairwise combinatorial matrix), Tier 4 (Scenario S2 lead generation, CLI help, JSON schema filtering), and REST API integration.

### 1.2 Independent Test & CLI Probes
1. **Pytest Profile Test Suite**:
   ```bash
   PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py -v
   # Output: 53 passed, 1 warning in 16.62s
   ```
2. **Pytest All Jobsearch Test Suites (Regression Probe)**:
   ```bash
   PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py
   # Output: 102 passed, 1 warning in 49.05s (Zero failures, zero regressions)
   ```
3. **CLI Options Probe**:
   ```bash
   PYTHONPATH=. uv run python -m cli.sense_jobs --help
   # Output: Exit code 0, complete option list rendered.
   ```
4. **CLI Mock Dry-Run Probe**:
   ```bash
   PYTHONPATH=. uv run python -m cli.sense_jobs --mock --dry-run
   # Output: Exit code 0, discovered 12 postings across all 10 boards, 10 Qualified, 1 Watching, 1 Excluded (SoundHound AI gated to 0% EXCLUDED).
   ```
5. **CLI JSON Stream Probe**:
   ```bash
   PYTHONPATH=. uv run python -m cli.sense_jobs --board openai --json
   # Output: Valid JSON array containing scored lead lead-openai-fde-01 with match breakdown.
   ```

---

## 2. Logic Chain

1. **Requirement R1 & Feature F1 (Candidate Profile Store & Taxonomy)**:
   - Observation: `core/jobsearch_profile.py` specifies all 44 CTO skills, 6 ML depth pillars, and compensation bounds matching Nate Walker's ratified profile.
   - Inference: Candidate profile store satisfies F1 and provides deterministic basis for scoring.
2. **Requirement R1 & Feature F2 (Dynamic Job Sourcing Engine)**:
   - Observation: `core/jobsearch_sourcing.py` implements all 10 target career board adapters (LinkedIn, Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS) and `JobSourcingEngine`.
   - Inference: Multi-board job sourcing and deduplication are fully implemented and conform to F2.
3. **Deterministic Scoring Engine & Employer Exclusion Gate**:
   - Observation: `compute_profile_match` evaluates postings across Role, Skills, ML Depth, Compensation, and Location, and enforces hard exclusion on former employers with risk flags.
   - Inference: Scoring mechanics are deterministic, resilient against malicious/malformed inputs, and satisfy boundary expectations.
4. **CLI & REST API Surfaces**:
   - Observation: CLI options in `cli/sense_jobs.py` and FastAPI endpoints in `api/routes/profile.py` execute cleanly and return validated schemas.
   - Inference: Interfaces are ready for operational sweeps and downstream frontend/SDK consumers.
5. **Integrity & Quality Assurance**:
   - Observation: Tests execute genuine logic against Pydantic models, adapters, and scoring functions without hardcoded assertions or facades.
   - Inference: Zero integrity violations; code quality is high.

---

## 3. Adversarial Challenges & Stress-Testing

### Challenge 1: Unstated vs. Sub-Floor Compensation Scoring
- **Assumption**: Postings without compensation data should not be penalized to 0, whereas postings explicitly below base floor ($180k) must be penalized and flagged.
- **Stress-Test**: Tested postings with `$130k-$170k` vs. `None/None`.
- **Result**: Sub-floor postings score 0 on compensation fit and trigger `compensation_below_minimum` (overall fit capped at realistic boundary), while unstated postings receive a neutral 7 pts and trigger `compensation_unstated`. **PASS**.

### Challenge 2: Former Employer Exclusion Bypass Prevention
- **Assumption**: Excluded employers (SoundHound AI, Amelia, IPsoft Amelia, Quant, IntelePeer) must not bypass the gate via casing, whitespace, or partial naming.
- **Stress-Test**: Tested multiple variations of former employer strings.
- **Result**: All variations normalize through `_canonical_employer` and `EXCLUDED_EMPLOYERS` gate, returning 0 fit score and `employer_excluded` risk flag. **PASS**.

### Challenge 3: HTML / XSS / Emoji Payload Sanitization
- **Assumption**: Scraped job descriptions often contain nested HTML markup, scripts, emojis, or unicode.
- **Stress-Test**: Tested posting containing `<script>alert('xss')</script>`, emojis, and HTML entities (`&quot;`, `&amp;`).
- **Result**: `_clean_html_text` strips script blocks and tags, normalizes whitespace, and extracts clean keywords without crashing or leaking markup into score explanations. **PASS**.

---

## 4. Pass/Refute Claim Verification Matrix

| Claim | Probe / Evidence | Result | Limitation |
|---|---|---|---|
| 44 Skills Taxonomy Partitioned into 22 Expert / 22 Advanced | `tests/test_jobsearch_profile.py::TestCandidateProfileStoreAndTaxonomy::test_skills_taxonomy_contains_at_least_40_skills_with_tier_partitioning` | **VERIFIED** | None |
| 6 Production ML Depth Pillars Configured | `tests/test_jobsearch_profile.py::TestCandidateProfileStoreAndTaxonomy::test_production_ml_depth_matrix_completeness` | **VERIFIED** | None |
| 10 Career Board Adapters Registered in `BOARD_REGISTRY` | `tests/test_jobsearch_profile.py::TestDynamicJobSourcingEngine::test_board_registry_contains_linkedin_and_all_9_target_employer_boards` | **VERIFIED** | None |
| Excluded Employers Hard Gate Scores 0 | `tests/test_jobsearch_profile.py::TestBoundariesAndNegativeCases::test_excluded_employers_score_zero_hard_gate` | **VERIFIED** | None |
| Pairwise 10-Case Combinatorial Matrix | `tests/test_jobsearch_profile.py::TestPairwiseCombinatorialMatrix::test_pairwise_scoring_matrix` | **VERIFIED** | None |
| CLI `--mock --dry-run` Discovers 12 Postings across 10 Boards | Direct shell execution of `python -m cli.sense_jobs --mock --dry-run` | **VERIFIED** | None |
| Zero Regressions Across Jobsearch Test Suites | `pytest tests/test_jobsearch_*.py` (102/102 tests passing) | **VERIFIED** | None |

---

## 5. Caveats

- **Offline Testing Mode**: Per repository standards, all tests and mock CLI sweeps execute in offline mode without live HTTP calls. When deploying live cron scrapers in production, ATS rate limits and API headers should be configured.
- **Milestone Scope**: Dedicated CRM ORM models (`LeadDB`, `OrganizationDB`, `OpportunityDB`) will be added in Milestone M2; profile persistence currently uses the existing `SettingsDB` JSON key-value store.

---

## 6. Conclusion

Milestone M1 satisfies all requirements set forth in `ORIGINAL_REQUEST.md` (R1) and `PROJECT.md` (Features F1, F2; Milestone M1):
- Candidate Profile Store & 44 CTO Skills Taxonomy are ratified and authoritative.
- Dynamic Job Sourcing Engine supports LinkedIn and all 9 target career boards.
- Scoring engine provides deterministic 0-100 fit evaluation with employer exclusion gating.
- CLI runner `cli/sense_jobs.py` and FastAPI profile routes are verified and functional.
- Test suites pass 102/102 with zero regressions.

**Final Verdict**: **APPROVE**

---

## 7. Verification Method

To reproduce independent verification:

```bash
cd /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

# 1. Run profile test suite
PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py -v

# 2. Run all jobsearch test suites for regression verification
PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py

# 3. Verify CLI execution
PYTHONPATH=. uv run python -m cli.sense_jobs --help
PYTHONPATH=. uv run python -m cli.sense_jobs --mock --dry-run
PYTHONPATH=. uv run python -m cli.sense_jobs --board openai --json
```
