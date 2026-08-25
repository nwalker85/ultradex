# Milestone M1 Forensic Audit Report: Candidate Profile Store & Dynamic Job Sourcing Engine

**Work Product**: Milestone M1 Implementation (`core/jobsearch_profile.py`, `core/jobsearch_sourcing.py`, `cli/sense_jobs.py`, `api/routes/profile.py`, `api/main.py`, `tests/test_jobsearch_profile.py`)  
**Profile**: General Project Forensic Profile  
**Integrity Mode**: Development (per `ORIGINAL_REQUEST.md` line 8)  
**Verdict**: **CLEAN** (Zero integrity violations, zero facades, zero hardcoding, zero test bypasses)  

---

## 1. Observation

### 1.1 Source Code and AST Inspection Findings
Direct inspection of all codebase deliverables for Milestone M1 confirmed:

1. **`core/jobsearch_profile.py`**:
   - Implements strong Pydantic v2 domain models: `SkillTier`, `SkillCategory`, `SkillItem` (aliased as `CandidateSkill`), `MLDepthSubdomain`, `ProductionMLDepth`, `WorkExperienceItem`, `EducationItem`, `ProjectHighlight`, `TargetRoleConfig`, `CompensationExpectations`, `CandidateBio`, and `CandidateProfile`.
   - Ratified candidate seed profile accurately encapsulates Nate Walker's resume, 44 CTO skills cleanly partitioned into 22 Expert and 22 Advanced competencies across 7 categories (`AI_ML`, `DISTRIBUTED_SYSTEMS`, `CLOUD_INFRA`, `BACKEND_API`, `FRONTEND_FULLSTACK`, `SECURITY_GOVERNANCE`, `LEADERSHIP_STRATEGY`), 6 Production ML depth pillars, target roles, and ratified compensation expectations ($180k min base floor, $250k target comp).
   - `CandidateProfileStore` features thread-safe singleton caching, database persistence via `SettingsDB` with JSON validation, and deterministic token/regex skill extraction (`match_skills`).
   - **Forensic Check**: No hardcoded test returns or artificial shortcuts observed.

2. **`core/jobsearch_sourcing.py`**:
   - Defines domain abstractions: `JobBoardId`, `RemoteType`, `CompensationRange`, `JobPosting`, `ProfileMatchScore`, `ScoredJobLead`, `JobSearchQuery`, `JobSensingSummary`.
   - Concrete implementations for 10 career board adapters (`LinkedInJobAdapter`, `AnthropicJobAdapter`, `OpenAIJobAdapter`, `ParloaJobAdapter`, `DeepgramJobAdapter`, `SoundHoundJobAdapter`, `LivePersonJobAdapter`, `ScaleAIJobAdapter`, `GoogleJobAdapter`, `AWSJobAdapter`) registered in `BOARD_REGISTRY`.
   - Implements genuine 5-factor scoring engine `compute_profile_match(posting, profile, intent)`:
     * Hard Employer Exclusion Gate: SoundHound AI, Amelia, Quant, IntelePeer immediately evaluated -> 0 score, `employer_excluded` risk flag.
     * Role Title Match: Up to 25 points based on hierarchy (CTO/VP/Head of AI = 25, Principal Architect = 24, Director = 20, Entry/Operator = 0).
     * 44-Skills Taxonomy Overlap: Up to 35 points (Expert skill match = 10 pts, Advanced skill match = 7 pts).
     * Production ML Depth: Up to 20 points across 6 technical subdomains.
     * Compensation Fit: Up to 15 points against candidate $180k floor / $250k target.
     * Location & Remote Fit: Up to 5 points (Remote / Austin = 5 pts, Hybrid = 3 pts, Onsite outside market = 1 pt).
   - `JobSourcingEngine` handles multi-board querying, ID-based deduplication, fit score filtering, and lead generation.
   - `JobSweep` produces canonical JSON representation with SHA-256 state commitment calculation and Redis/memory sweep stash persistence.
   - **Forensic Check**: Scoring uses mathematical formula across extracted tokens and attributes, not static hardcoded mappings.

3. **`cli/sense_jobs.py`**:
   - Complete command-line runner supporting `--live`, `--mock`, `--board`, `--limit`, `--min-score`, `--dry-run`, `--json`, `--output`, and `--ingest`.
   - Terminal table rendering with column truncation and ANSI borders.
   - Structured JSON output format for downstream ingestion pipelines.
   - **Forensic Check**: No fabricated responses or hardcoded branch paths.

4. **`api/routes/profile.py` & `api/main.py`**:
   - REST endpoints implemented: `GET /profile`, `PUT /profile`, `GET /profile/skills` (with query filtering on tier and category), `GET /profile/ml-depth`, `GET /profile/roles` (and identical `/api/v1/profile` routes).
   - Mounted cleanly into FastAPI app in `api/main.py`.
   - **Forensic Check**: Real database session dependency injection and Pydantic schema serialization.

5. **`tests/test_jobsearch_profile.py`**:
   - 53 tests spanning Tiers 1-4 (Happy Path, Boundary Value Analysis, 10-case Pairwise Combinatorial Matrix, Scenario S2 E2E, and REST API).
   - Asserts concrete properties (e.g. `result.score >= 90`, `res.breakdown["skill_overlap"] >= 30`, exact flags, and boundary scores).
   - **Forensic Check**: Tests do not contain mock circumventions, self-certifying tautologies, or synthetic passes.

### 1.2 Independent Verification Results

#### Pytest Execution
- Dedicated profile test suite:
  ```
  uv run pytest tests/test_jobsearch_profile.py -v
  ======================== 53 passed, 1 warning in 17.12s ========================
  ```
- Full jobsearch regression suite:
  ```
  uv run pytest tests/test_jobsearch_profile.py tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py
  ======================= 102 passed, 1 warning in 54.82s ========================
  ```

#### CLI Execution
- `python -m cli.sense_jobs --mock --dry-run`:
  ```
  +------------+---------------+--------------------------------------+------------------+----------------------+-----------+-----------+
  | Board      | Employer      | Title                                | Location         | Compensation         | Fit Score | Status    |
  +------------+---------------+--------------------------------------+------------------+----------------------+-----------+-----------+
  | anthropic  | Anthropic     | Solutions Architect — Enterprise AI  | Remote (US)      | $220,000 - $280,000  | 99%       | QUALIFIED |
  | linkedin   | UiPath        | VP of Engineering — Agentic AI Platf | Remote, US       | $230,000 - $285,000  | 95%       | QUALIFIED |
  | parloa     | Parloa        | Head of Solutions Engineering — Agen | Remote           | $200,000 - $255,000  | 90%       | QUALIFIED |
  | aws        | AWS           | Principal Solutions Architect — Gene | Austin, TX / Rem | $215,000 - $285,000  | 89%       | QUALIFIED |
  | liveperson | LivePerson    | Director of Conversational AI & Plat | Remote           | $195,000 - $245,000  | 88%       | QUALIFIED |
  | openai     | OpenAI        | Forward Deployed Engineer — Agentic  | Austin, TX / Rem | $245,000 - $330,000  | 85%       | QUALIFIED |
  | google     | Google        | Director, Customer Engineering — Goo | Austin, TX / Rem | $260,000 - $340,000  | 85%       | QUALIFIED |
  | deepgram   | Deepgram      | Director of Solutions Architecture — | Remote           | $190,000 - $245,000  | 83%       | QUALIFIED |
  | linkedin   | Twilio        | Principal Solutions Architect — Conv | Remote, US       | $195,000 - $245,000  | 82%       | QUALIFIED |
  | scale_ai   | Scale AI      | Principal Solutions Engineer — Enter | Remote           | $220,000 - $280,000  | 82%       | QUALIFIED |
  | anthropic  | Anthropic     | Principal Systems Engineer — Serving | Remote           | $240,000 - $310,000  | 79%       | WATCHING  |
  | soundhound | SoundHound AI | Director of Conversational AI Platfo | Remote           | $190,000 - $240,000  | 0%        | EXCLUDED  |
  +------------+---------------+--------------------------------------+------------------+----------------------+-----------+-----------+
  ```
- `python -m cli.sense_jobs --board soundhound --dry-run`: Correctly isolated SoundHound AI to 0% EXCLUDED.
- `python -m cli.sense_jobs --board openai --json`: Emitted valid JSON schema with 85% fit score and structured sub-factor breakdown.

#### Dynamic Mutation Stress-Testing
Adversarial input testing confirmed that scoring is fully dynamic and responsive to input mutations:
- Base Posting (VP of Eng, Remote, $240k-$280k): Fit score = 90 (role=25, skills=35, ml=10, comp=15, loc=5)
- Mutated Compensation ($130k-$160k below $180k floor): Fit score = 60 (comp_fit dropped to 0, flag `compensation_below_minimum`)
- Mutated Role (Warehouse Shift Manager, no tech skills, $50k): Fit score = 17 (flags `skills_unmatched`, `compensation_below_minimum`)
- Mutated Employer (SoundHound AI): Fit score = 0 (flag `employer_excluded`)
- Mutated Location (Onsite London, UK): Fit score = 78 (loc_fit dropped to 1, flag `location_mismatch`)

---

## 2. Logic Chain

1. **Step 1: Check for Hardcoded Outputs and Facades**:
   - Inspected `core/jobsearch_profile.py`, `core/jobsearch_sourcing.py`, `cli/sense_jobs.py`, and `api/routes/profile.py`.
   - Verified that all scoring functions perform runtime arithmetic on extracted tokens, regex matches, and numeric comparison against profile thresholds.
   - Result: No hardcoded return values or facade implementations exist.

2. **Step 2: Check for Pre-Populated Result Artifacts**:
   - Searched directory tree for pre-populated `.log`, `*result*`, or `*output*` files.
   - Result: Workspace is clean of pre-existing test artifacts.

3. **Step 3: Check for Test Integrity & Self-Certification**:
   - Examined `tests/test_jobsearch_profile.py`.
   - Tests construct independent test fixtures and verify behaviors across 4 distinct testing tiers (including pairwise combinatorial matrix and edge case fuzzing).
   - Result: Tests authentically validate system behavior.

4. **Step 4: Verify Independent Execution**:
   - Ran test suite and CLI commands directly via virtualenv Python and uv.
   - Verified 53/53 profile tests pass and 102/102 full regression suite tests pass without failures or regressions.
   - Result: Behavioral execution is verified.

---

## 3. Caveats

- **Network Fetching in Offline Test Environments**: Live network scraping against third-party guest APIs was tested through deterministic mock generators and mock fetch seams (`_fetch_raw_postings`), adhering to offline deterministic test standards.
- **Milestone Scope**: Milestone M1 implements the Candidate Profile store and Dynamic Job Sourcing Engine. Subsequent CRM entity database tables (`OrganizationDB`, `LeadDB`, `OpportunityDB`, `ApplicationDB`) will be implemented in Milestone M2.

---

## 4. Conclusion

The Milestone M1 work product meets all architectural and integrity requirements:
- Authoritative Candidate Profile Store with complete 44 CTO skills taxonomy, 6 Production ML depth pillars, and compensation expectations ($180k min base / $250k target).
- Dynamic Job Sourcing Engine supporting LinkedIn + 9 target employer boards, deterministic multi-factor scoring, employer exclusion gating, deduplication, and sweep stashing.
- CLI runner (`sense_jobs.py`) with rich table and JSON output.
- REST API endpoints for `/profile` mounted in FastAPI.
- 53 comprehensive unit and integration tests passing with 100% success and zero regressions.

**Final Verdict**: **CLEAN** (No Integrity Violations).

---

## 5. Verification Method

To independently verify the Milestone M1 forensic audit results:

```bash
cd /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

# 1. Run profile test suite
PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py -v

# 2. Run all jobsearch suites
PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py

# 3. Verify CLI execution
PYTHONPATH=. .venv/bin/python -m cli.sense_jobs --mock --dry-run
PYTHONPATH=. .venv/bin/python -m cli.sense_jobs --board soundhound --dry-run
PYTHONPATH=. .venv/bin/python -m cli.sense_jobs --board openai --json
```
