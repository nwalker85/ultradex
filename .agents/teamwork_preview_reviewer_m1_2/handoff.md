# Milestone M1 Independent Review & Adversarial Challenge Report

**Reviewer**: Milestone M1 Reviewer 2 (Replacement)  
**Target Milestone**: M1 (Candidate Profile Store & Skills Taxonomy + Dynamic Job Sourcing Engine)  
**Specification Reference**: `PROJECT.md` (§F1, §F2, §M1) & `ORIGINAL_REQUEST.md` (§R1)  
**Target Directory**: `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req`  
**Verdict**: **APPROVE**

---

## 1. Observation

### 1.1 Direct Source Code Inspections

1. **`core/jobsearch_profile.py`**:
   - **44-Skill Taxonomy Partitioning**: Lines 232–636 implement `_build_skills_taxonomy()`, returning exactly 44 skills:
     - **22 Expert Skills**: LLM Systems, Multi-Agent Systems, Conversational AI, Voice AI / ASR / TTS, RAG & Vector Retrieval, Platform Architecture, Python, FastAPI, TypeScript, Event-Driven Systems & Messaging, NATS / JetStream, CQRS & Event Sourcing, GraphQL, PostgreSQL, Redis, Docker, Kubernetes & k0s/k3s, Linux Systems & Bare Metal, Telephony & CPaaS, Engineering Leadership, Enterprise Solutions Architecture, Test-Driven Development.
     - **22 Advanced Skills**: Fine-Tuning & PEFT, Embeddings & Semantic Search, Model Quantization & vLLM, Multimodal AI, PyTorch, Rust, Go, SvelteKit, Tailwind CSS, Cloudflare & Edge Compute, AWS Cloud Architecture, Security & IAM, Cryptographic Receipts, Observability & OpenTelemetry, Vector Databases, Git & Repository Governance, Regulatory Compliance, Executive Stakeholder Communication, Vendor Evaluation & TCO, Audio DSP & Acoustic Processing, Information Retrieval & BM25, High Availability & Disaster Recovery.
     - **7 Skill Categories**: `SkillCategory` enum (lines 25–33) defines `AI_ML`, `DISTRIBUTED_SYSTEMS`, `CLOUD_INFRA`, `BACKEND_API`, `FRONTEND_FULLSTACK`, `SECURITY_GOVERNANCE`, `LEADERSHIP_STRATEGY`.
   - **6 Production ML Depth Pillars**: Lines 639–704 implement `_build_production_ml_depth()`, configuring:
     - `llm_orchestration`: LLM Orchestration & Systems (Claude, OpenAI, DeepSeek, vLLM, Ollama)
     - `asr_tts_voice`: Speech & Sovereign Voice AI (ASR/TTS) (Gjallarhorn, Whisper, Kokoro, Piper, WebRTC, SIP, MQTT)
     - `fine_tuning_adaptation`: Fine-Tuning & Parameter-Efficient ML (LoRA, QLoRA, TRL/PEFT, PyTorch, Axolotl, Unsloth)
     - `embeddings_rag`: Embeddings & Hybrid RAG Architecture (SentenceTransformers, BGE-M3, Qdrant, pgvector, Cross-Encoders, RRF)
     - `agent_loops_tooling`: Agent Loops & Tool Sandboxing (MCP, ReAct, Bifrost, Docker sandboxes)
     - `inference_hardware`: Inference Hardware & Local Compute (RTX 4090, CUDA, TensorRT-LLM, vLLM, GGUF/llama.cpp, bare-metal k0s/k3s)
   - **Compensation Bounds**: Lines 136–154 (`CompensationExpectations`) and lines 855–864 establish min base `$180,000 USD`, target total comp `$250,000 USD`, min total comp `$200,000 USD`, with helper validation methods `is_acceptable()` and `meets_target()`.
   - **Candidate Profile Store**: Lines 874–962 implement `CandidateProfileStore` with thread-safe singleton in-memory caching, fallback persistence to `SettingsDB`, and deterministic `match_skills(text)`.

2. **`core/jobsearch_sourcing.py`**:
   - **10 Career Board Adapters**: Lines 569–839 implement and register in `BOARD_REGISTRY` all 10 adapters:
     - `LinkedInJobAdapter` (`linkedin`)
     - `AnthropicJobAdapter` (`anthropic`)
     - `OpenAIJobAdapter` (`openai`)
     - `ParloaJobAdapter` (`parloa`)
     - `DeepgramJobAdapter` (`deepgram`)
     - `SoundHoundJobAdapter` (`soundhound`)
     - `LivePersonJobAdapter` (`liveperson`)
     - `ScaleAIJobAdapter` (`scale_ai`)
     - `GoogleJobAdapter` (`google`)
     - `AWSJobAdapter` (`aws`)
   - **Hard Employer Exclusion Gate**: Lines 202–246 implement `compute_profile_match()`, gating former employers (`SoundHound AI`, `Amelia`, `IPsoft Amelia`, `Quant`, `IntelePeer`) immediately to fit score `0`, breakdown zeroes, and risk flag `employer_excluded`.
   - **Deterministic 5-Factor Scoring**:
     - Role Match: max 25 pts (lines 256–315)
     - Skills Taxonomy Overlap: max 35 pts with Expert weighted higher than Advanced (lines 316–345)
     - Production ML Depth: max 20 pts (lines 346–418)
     - Compensation Fit: max 15 pts (lines 425–455)
     - Location & Remote Fit: max 5 pts (lines 456–470)
   - **State Commitment & Sweep Stash**: Lines 979–1059 (`JobSweep`) compute deterministic SHA-256 state commitments over normalized JSON payloads and stash declarations in Redis / in-memory stashes.

3. **`cli/sense_jobs.py`**:
   - Lines 98–244 implement CLI runner with full argument parsing (`--live`, `--mock`, `--board`, `--limit`, `--min-score`, `--dry-run`, `--json`, `--output`, `--ingest`), ASCII table formatting, and integration with `JobSourcingEngine` and `JobSweep`.

4. **`api/routes/profile.py` & `api/main.py`**:
   - Lines 18–72 expose `GET /profile`, `PUT /profile`, `GET /profile/skills`, `GET /profile/ml-depth`, `GET /profile/roles` (and matching `/api/v1/profile` routes), mounted cleanly in FastAPI app.

5. **`tests/test_jobsearch_profile.py`**:
   - 706 lines of exhaustive test cases spanning Tiers 1–4, boundary value analysis, pairwise combinations, E2E CLI scenarios, and REST API endpoints.

---

### 1.2 Independent Test Execution & Tool Results

1. **Profile Test Suite Execution**:
   - Command: `PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py -v`
   - Output: `53 passed, 1 warning in 21.10s` (exit code `0`).
   - All 53 tests passed cleanly across Profile Store, 44-Skill Taxonomy, 6 ML Depth pillars, Compensation bands, 10 Board Adapters, Deterministic Match Scoring, Boundary Values, Pairwise Matrix, E2E CLI Scenario, and REST APIs.

2. **Full Jobsearch Regression Suite Execution**:
   - Command: `PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py`
   - Output: `102 passed, 1 warning in 55.17s` (exit code `0`).
   - Zero regressions across existing executors, intent parsing, and scoring test suites.

3. **CLI Execution Verifications**:
   - `python -m cli.sense_jobs --mock --dry-run`: Outputted formatted table of 12 discovered postings across 10 boards with Anthropic (99%), UiPath (95%), Parloa (90%), AWS (89%), LivePerson (88%), OpenAI (85%), Google (85%), Deepgram (83%), Twilio (82%), Scale AI (82%) qualified, and SoundHound AI (0%) excluded.
   - `python -m cli.sense_jobs --board anthropic --dry-run`: Outputted Anthropic postings (99% Solutions Architect, 79% Principal Systems Engineer).

---

## 2. Logic Chain

1. **Taxonomy & Depth Alignment**:
   - The 44 skills are partitioned into exactly 22 Expert and 22 Advanced competencies distributed across 7 distinct technical and leadership categories.
   - The 6 Production ML depth pillars provide deep technical details (technologies, architectural patterns, production milestones) for LLM Orchestration, Sovereign Voice AI, Fine-Tuning, Hybrid RAG, Agent Loops/MCP, and Hardware Inference.
   - Compensation is configured strictly at `$180k` min base, `$250k` target, and `$200k` minimum total.

2. **Adapter Architecture & Board Coverage**:
   - All 10 required boards (LinkedIn + Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS) are implemented as subclasses of `JobBoardAdapter` and registered in `BOARD_REGISTRY`.
   - Each adapter normalizes board-specific fields into the canonical `JobPosting` schema with robust salary parsing (`_parse_salary_range`).

3. **Scoring Rigor & Hard Exclusion Gate**:
   - The match scoring algorithm computes deterministic 0–100 integer scores across 5 independent dimensions (role 25, skills 35, ML depth 20, comp 15, location 5).
   - Expert skills carry higher point weights than Advanced skills.
   - The employer exclusion gate evaluates candidate company names and canonical forms, ensuring former employers (SoundHound/Amelia, Quant, IntelePeer) are intercepted and gated to 0% fit with `employer_excluded` risk flag before any scoring calculations execute.

4. **Integrity & Code Quality Audit**:
   - **No Hardcoded Test Results**: Scoring is computed dynamically via regex token matching, skill dictionary lookups, and bounded arithmetic.
   - **No Dummy/Facade Implementations**: Complete implementations exist for profile store, caching, database persistence, board adapters, scoring functions, and CLI tooling.
   - **No Task Bypasses**: The implementation builds the domain natively on FastAPI, Pydantic, and SQLAlchemy without taking unapproved shortcuts.
   - **Deterministic & Offline**: All tests run 100% offline using mock adapters and data fixtures.

---

## 3. Caveats

- **Live Guest Scraping & Rate Limits**: In `--live` mode, career board scraping queries external public endpoints and ATS guest APIs. In production, rate limits or proxies should be monitored for large-scale polling. Offline test suites use isolated mock seams (`_fetch_raw_postings`).
- **Profile Database Storage**: In Milestone M1, candidate profile persistence leverages `SettingsDB` with JSON serialization to avoid premature database migrations prior to Milestone M2's formal CRM ORM models (`LeadDB`, `OrganizationDB`, etc.).

---

## 4. Conclusion

The Milestone M1 deliverables strictly satisfy all requirements outlined in `PROJECT.md` (§F1, §F2) and `ORIGINAL_REQUEST.md` (§R1):
- Complete 44-skill taxonomy (22 Expert, 22 Advanced across 7 categories).
- 6 Production ML depth pillars.
- Verified compensation bounds ($180k min base / $250k target).
- All 10 career board adapters implemented and registered.
- Hard employer exclusion gate verified.
- 53/53 profile tests and 102/102 total jobsearch tests passing with zero regressions.

**Final Verdict**: **APPROVE**

---

## 5. Verification Method

To independently verify the Milestone M1 implementation:

```bash
cd /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req

# 1. Run profile and sourcing test suite (53 tests)
PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py -v

# 2. Run full regression jobsearch test suites (102 tests)
PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py

# 3. Verify CLI execution
PYTHONPATH=. uv run python -m cli.sense_jobs --mock --dry-run
PYTHONPATH=. uv run python -m cli.sense_jobs --board anthropic --dry-run
PYTHONPATH=. uv run python -m cli.sense_jobs --board soundhound --dry-run
```
