"""Tests for Candidate Profile Store, Skills Taxonomy, Dynamic Job Sourcing CLI,
and Profile Fit Scoring Engine (CCC Milestone M1, Requirement R1).

Verifies Features F1 and F2:
- Authoritative Candidate Profile store seeded with Nate Walker's resume,
  40+ CTO skills taxonomy (Expert/Advanced), production ML depth, target roles,
  and compensation expectations ($180k base / $250k target).
- Dynamic job sourcing in `cli/sense_jobs.py` across LinkedIn and 9 target
  career boards: Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson,
  Scale AI, Google, AWS.
- Pure deterministic fit scoring engine (0-100) with exact match breakdown.
- Boundary conditions, negative inputs, salary parsing, and CLI JSON formatting.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.jobsearch_profile import (
    CandidateBio,
    CandidateProfile,
    CandidateProfileStore,
    CandidateSkill,
    CompensationExpectations,
    ProductionMLDepth,
    SkillCategory,
    SkillItem,
    SkillTier,
    TargetRoleConfig,
    get_ratified_candidate_profile,
)
from cli.sense_jobs import (
    BOARD_REGISTRY,
    JobPosting,
    JobSourcingEngine,
    ProfileMatchScore,
    compute_profile_match,
    main as sense_jobs_main,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def profile_store() -> CandidateProfileStore:
    """Provides a freshly instantiated CandidateProfileStore with default seed."""
    CandidateProfileStore._cached_profile = None
    return CandidateProfileStore()


@pytest.fixture
def candidate_profile(profile_store: CandidateProfileStore) -> CandidateProfile:
    """Provides the authoritative Nate Walker candidate profile."""
    return profile_store.get_profile()


@pytest.fixture
def mock_anthropic_posting() -> JobPosting:
    """Representative high-fit job posting from Anthropic."""
    return JobPosting(
        id="anthropic-sa-01",
        employer="Anthropic",
        title="Solutions Architect — Enterprise AI & Multi-Agent Systems",
        location="Remote (US)",
        description=(
            "We are seeking a Principal Solutions Architect to design and deploy "
            "enterprise conversational AI and agentic orchestration platforms. "
            "Requires deep expertise in LLM systems, Python, FastAPI, distributed systems, "
            "and production RAG pipelines."
        ),
        required_skills=[
            "Conversational AI",
            "Multi-Agent Systems",
            "Python",
            "FastAPI",
            "LLM Systems",
            "Distributed Systems",
        ],
        salary_min=220_000,
        salary_max=280_000,
        salary_currency="USD",
        url="https://jobs.lever.co/anthropic/anthropic-sa-01",
        source_board="anthropic",
        posted_at="2026-08-20T10:00:00Z",
    )


# ============================================================================
# TIER 1: HAPPY PATH — PROFILE STORE & 40+ SKILLS TAXONOMY (F1)
# ============================================================================

class TestCandidateProfileStoreAndTaxonomy:
    """Verifies Candidate Profile store seed, taxonomy partitioning, and ML depth."""

    def test_profile_store_returns_authoritative_nate_walker_profile(
        self, candidate_profile: CandidateProfile
    ):
        """F1.1: Store returns Nate Walker's candidate profile with all required sections."""
        assert candidate_profile.candidate_name == "Nate Walker"
        assert "CTO" in candidate_profile.title or "VP" in candidate_profile.title
        assert len(candidate_profile.resume_text) > 200
        assert len(candidate_profile.target_roles) >= 4
        assert len(candidate_profile.target_domains) >= 5

    def test_skills_taxonomy_contains_at_least_40_skills_with_tier_partitioning(
        self, candidate_profile: CandidateProfile
    ):
        """F1.2: Skills taxonomy has >=40 skills cleanly partitioned into Expert and Advanced."""
        skills = candidate_profile.skills
        assert len(skills) >= 40, f"Expected >= 40 skills, got {len(skills)}"

        expert_skills = [s for s in skills.values() if s.tier == SkillTier.EXPERT]
        advanced_skills = [s for s in skills.values() if s.tier == SkillTier.ADVANCED]

        assert len(expert_skills) >= 15, "Expected >= 15 Expert skills"
        assert len(advanced_skills) >= 15, "Expected >= 15 Advanced skills"
        assert len(expert_skills) + len(advanced_skills) == len(skills)

    def test_skills_taxonomy_contains_core_cto_and_voice_ai_competencies(
        self, candidate_profile: CandidateProfile
    ):
        """F1.3: Verifies essential core competencies exist in the taxonomy."""
        skill_names = {s.name.lower() for s in candidate_profile.skills.values()}
        required_core = {
            "conversational ai",
            "voice ai / asr / tts",
            "multi-agent systems",
            "platform architecture",
            "llm systems",
            "python",
            "fastapi",
            "graphql",
            "postgresql",
            "sveltekit",
            "docker",
            "nats / jetstream",
        }
        missing = required_core - skill_names
        assert not missing, f"Missing required core skills in taxonomy: {missing}"

    def test_production_ml_depth_matrix_completeness(
        self, candidate_profile: CandidateProfile
    ):
        """F1.4: Production ML depth matrix specifies deep production capabilities across 6 pillars."""
        ml = candidate_profile.production_ml
        assert isinstance(ml, ProductionMLDepth)
        assert len(ml.llm_systems) >= 3
        assert len(ml.agentic_orchestration) >= 3
        assert len(ml.voice_speech_ai) >= 3
        assert len(ml.rag_vector_search) >= 3
        assert len(ml.fine_tuning_evals) >= 2
        assert len(ml.edge_quantization) >= 2

    def test_compensation_expectations_configuration(
        self, candidate_profile: CandidateProfile
    ):
        """F1.5: Compensation bounds match ratified $180k min base / $250k target."""
        comp = candidate_profile.compensation
        assert isinstance(comp, CompensationExpectations)
        assert comp.min_base == 180_000
        assert comp.target_total == 250_000
        assert comp.currency == "USD"
        assert comp.is_acceptable(200_000) is True
        assert comp.is_acceptable(170_000) is False
        assert comp.meets_target(260_000) is True
        assert comp.meets_target(220_000) is False

    def test_profile_store_update_and_cache(self, profile_store: CandidateProfileStore):
        """F1.6: Updating profile correctly updates cached instance."""
        prof = profile_store.get_profile()
        prof.candidate_name = "Nathaniel Walker"
        updated = profile_store.update_profile(prof)
        assert updated.candidate_name == "Nathaniel Walker"
        assert profile_store.get_profile().candidate_name == "Nathaniel Walker"


# ============================================================================
# TIER 1: HAPPY PATH — DYNAMIC JOB SOURCING (F2) & 9 TARGET BOARDS
# ============================================================================

class TestDynamicJobSourcingEngine:
    """Verifies job sourcing across LinkedIn and all 9 target employer boards."""

    def test_board_registry_contains_linkedin_and_all_9_target_employer_boards(self):
        """F2.1: Registry covers LinkedIn + 9 target employer career boards."""
        expected_boards = {
            "linkedin",
            "anthropic",
            "openai",
            "parloa",
            "deepgram",
            "soundhound",
            "liveperson",
            "scale_ai",
            "google",
            "aws",
        }
        registered = set(BOARD_REGISTRY.keys())
        assert expected_boards <= registered, f"Missing career boards: {expected_boards - registered}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "board_name",
        [
            "linkedin",
            "anthropic",
            "openai",
            "parloa",
            "deepgram",
            "soundhound",
            "liveperson",
            "scale_ai",
            "google",
            "aws",
        ],
    )
    async def test_adapter_scrapes_and_normalizes_postings_for_every_board(
        self, board_name: str, candidate_profile: CandidateProfile
    ):
        """F2.2: Each board adapter successfully parses raw board response into JobPosting."""
        adapter = BOARD_REGISTRY[board_name]()
        mock_raw_data = {
            "title": f"Staff AI Engineer ({board_name.title()})",
            "location": "Remote, US",
            "description": "Building next-generation voice AI and agentic systems using Python and FastAPI.",
            "salary": "$190,000 - $260,000",
            "url": f"https://careers.{board_name}.com/jobs/123",
        }

        with patch.object(adapter, "_fetch_raw_postings", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [mock_raw_data]
            postings = await adapter.scrape_postings(
                target_roles=candidate_profile.target_roles,
                target_domains=candidate_profile.target_domains,
            )

            assert len(postings) == 1
            posting = postings[0]
            assert isinstance(posting, JobPosting)
            assert posting.source_board == board_name
            assert posting.title == f"Staff AI Engineer ({board_name.title()})"
            assert posting.salary_min == 190_000
            assert posting.salary_max == 260_000

    @pytest.mark.asyncio
    async def test_sourcing_engine_queries_target_roles_and_aggregates_results(
        self, candidate_profile: CandidateProfile
    ):
        """F2.3: Sourcing engine queries candidate profile target roles and aggregates results."""
        engine = JobSourcingEngine(candidate_profile=candidate_profile)
        with patch.object(engine, "_scrape_board", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = [
                JobPosting(
                    id="mock-1",
                    employer="Anthropic",
                    title="Solutions Architect",
                    location="Remote",
                    description="Enterprise AI",
                    required_skills=["Python", "FastAPI"],
                    salary_min=200_000,
                    salary_max=260_000,
                    salary_currency="USD",
                    url="https://anthropic.com/job/1",
                    source_board="anthropic",
                    posted_at="2026-08-20T10:00:00Z",
                )
            ]
            results = await engine.source_all_boards(boards=["anthropic", "openai"])
            assert len(results) >= 1
            assert results[0].employer == "Anthropic"


# ============================================================================
# TIER 1: HAPPY PATH — PROFILE MATCH & SCORING ENGINE
# ============================================================================

class TestProfileMatchAndScoringEngine:
    """Verifies deterministic fit scoring (0-100) and breakdown mechanics."""

    def test_perfect_fit_role_scores_above_90_with_breakdown(
        self, mock_anthropic_posting: JobPosting, candidate_profile: CandidateProfile
    ):
        """F1/F2 scoring: High role overlap, expert skills, target comp, and remote location."""
        result = compute_profile_match(mock_anthropic_posting, candidate_profile)
        assert isinstance(result, ProfileMatchScore)
        assert result.score >= 90
        assert result.breakdown["role_fit"] >= 20
        assert result.breakdown["skill_overlap"] >= 30
        assert result.breakdown["ml_depth"] >= 15
        assert result.breakdown["compensation_fit"] >= 12
        assert result.breakdown["location_fit"] == 5
        assert "employer_excluded" not in result.risk_flags
        assert "Strong match" in result.explanation or "fit" in result.explanation

    def test_expert_skills_yield_higher_weight_than_advanced_skills(
        self, candidate_profile: CandidateProfile
    ):
        """Scoring logic: Expert skills have higher weight multiplier than Advanced."""
        expert_posting = JobPosting(
            id="exp-01",
            employer="Scale AI",
            title="Principal Engineer",
            location="Remote",
            description="Seeking Conversational AI and Multi-Agent Systems leader.",
            required_skills=["Conversational AI", "Multi-Agent Systems"],  # Expert
            salary_min=200_000,
            salary_max=250_000,
            salary_currency="USD",
            url="https://scale.com/1",
            source_board="scale_ai",
            posted_at="2026-08-20T10:00:00Z",
        )
        advanced_posting = JobPosting(
            id="adv-01",
            employer="Scale AI",
            title="Principal Engineer",
            location="Remote",
            description="Seeking Rust and PyTorch engineer.",
            required_skills=["Rust", "PyTorch"],  # Advanced
            salary_min=200_000,
            salary_max=250_000,
            salary_currency="USD",
            url="https://scale.com/2",
            source_board="scale_ai",
            posted_at="2026-08-20T10:00:00Z",
        )

        expert_res = compute_profile_match(expert_posting, candidate_profile)
        advanced_res = compute_profile_match(advanced_posting, candidate_profile)

        assert expert_res.breakdown["skill_overlap"] > advanced_res.breakdown["skill_overlap"]


# ============================================================================
# TIER 2: BOUNDARY VALUE ANALYSIS & NEGATIVE TEST CASES
# ============================================================================

class TestBoundariesAndNegativeCases:
    """Verifies edge cases, out-of-range comp, unknown boards, exclusions, and text sanitation."""

    @pytest.mark.parametrize(
        ("salary_min", "salary_max", "expected_comp_score_min", "expected_flag"),
        [
            (260_000, 300_000, 15, None),                         # Above target ($250k) -> Max score
            (250_000, 270_000, 14, None),                         # At target ($250k) -> High score
            (180_000, 210_000, 10, None),                         # At base ($180k) -> Passing score
            (130_000, 170_000, 0, "compensation_below_minimum"),  # Below base ($180k) -> Flagged & 0
            (None, None, 7, "compensation_unstated"),             # Unstated -> Neutral score & Flag
        ],
    )
    def test_compensation_boundary_scoring_bands(
        self,
        salary_min: int | None,
        salary_max: int | None,
        expected_comp_score_min: int,
        expected_flag: str | None,
        candidate_profile: CandidateProfile,
    ):
        """BVA: Tests compensation step boundaries ($180k min base, $250k target)."""
        posting = JobPosting(
            id="comp-test",
            employer="Deepgram",
            title="Solutions Architect — Voice AI",
            location="Remote",
            description="Voice AI solutions.",
            required_skills=["Voice AI / ASR / TTS"],
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD",
            url="https://deepgram.com/jobs/1",
            source_board="deepgram",
            posted_at="2026-08-20T10:00:00Z",
        )
        res = compute_profile_match(posting, candidate_profile)
        if expected_comp_score_min > 0:
            assert res.breakdown["compensation_fit"] >= expected_comp_score_min
        else:
            assert res.breakdown["compensation_fit"] == 0

        if expected_flag:
            assert expected_flag in res.risk_flags
        else:
            assert "compensation_below_minimum" not in res.risk_flags

    @pytest.mark.parametrize(
        "excluded_employer",
        ["SoundHound AI", "soundhound", "Amelia", "IPsoft Amelia", "Quant", "IntelePeer"],
    )
    def test_excluded_employers_score_zero_hard_gate(
        self, excluded_employer: str, candidate_profile: CandidateProfile
    ):
        """Hard Gate: Excluded employers always score 0 with employer_excluded risk flag."""
        posting = JobPosting(
            id="excl-01",
            employer=excluded_employer,
            title="VP of AI Platform & Conversational Engineering",
            location="Remote",
            description="Conversational AI, Voice AI, Python, FastAPI, Multi-Agent Systems.",
            required_skills=["Conversational AI", "Python", "FastAPI"],
            salary_min=250_000,
            salary_max=300_000,
            salary_currency="USD",
            url="https://careers.com/1",
            source_board="soundhound",
            posted_at="2026-08-20T10:00:00Z",
        )
        res = compute_profile_match(posting, candidate_profile)
        assert res.score == 0
        assert "employer_excluded" in res.risk_flags
        assert "excluded: employer in exclusions" in res.explanation.lower()

    def test_completely_irrelevant_job_scores_zero(
        self, candidate_profile: CandidateProfile
    ):
        """Irrelevant role (e.g. Forklift Operator) scores 0 with unmatched flags."""
        posting = JobPosting(
            id="irrel-01",
            employer="General Logistics Inc",
            title="Night Shift Forklift Operator & Warehouse Associate",
            location="Onsite — Cleveland, OH",
            description="Operate heavy machinery, pallet jacks, and inventory logging.",
            required_skills=["Forklift Certified", "OSHA 10"],
            salary_min=45_000,
            salary_max=52_000,
            salary_currency="USD",
            url="https://logistics.com/job/1",
            source_board="linkedin",
            posted_at="2026-08-20T10:00:00Z",
        )
        res = compute_profile_match(posting, candidate_profile)
        assert res.score == 0
        assert "role_unmatched" in res.risk_flags
        assert "skills_unmatched" in res.risk_flags
        assert "compensation_below_minimum" in res.risk_flags

    def test_unregistered_or_invalid_board_name_raises_value_error(self):
        """Negative: Sourcing engine rejects unknown career board names."""
        engine = JobSourcingEngine()
        with pytest.raises(ValueError, match="Unsupported career board: 'invalid_board'"):
            engine.get_adapter("invalid_board")

    def test_robust_text_sanitation_with_html_emojis_and_unicode(
        self, candidate_profile: CandidateProfile
    ):
        """Sanitation: Scraper & matcher cleanly handle HTML tags, emojis, and special chars."""
        messy_posting = JobPosting(
            id="messy-01",
            employer="Parloa",
            title="<b>Head of Solutions Engineering</b> — 🚀 Agentic Voice AI! 🤖",
            location="Remote &amp; Austin TX",
            description=(
                "<p>Join us at <strong>Parloa</strong>! We are scaling <script>alert('xss')</script> "
                "conversational AI & multi-agent systems with Python / FastAPI. 🌟 "
                "Comp: $240k–$280k + equity! &quot;Work from anywhere&quot;.</p>"
            ),
            required_skills=["Conversational AI", "FastAPI", "Python"],
            salary_min=240_000,
            salary_max=280_000,
            salary_currency="USD",
            url="https://parloa.com/careers/1",
            source_board="parloa",
            posted_at="2026-08-20T10:00:00Z",
        )
        res = compute_profile_match(messy_posting, candidate_profile)
        assert res.score >= 80
        assert "<script>" not in res.explanation
        assert "alert(" not in res.explanation


# ============================================================================
# TIER 3: PAIRWISE COMBINATORIAL MATRIX
# ============================================================================

class TestPairwiseCombinatorialMatrix:
    """Pairwise combinatorial verification across boards, skills, comp, location, and exclusions."""

    @pytest.mark.parametrize(
        ("board", "skill_overlap_kind", "salary_range", "location", "is_excluded", "expected_min_score", "expected_max_score"),
        [
            ("anthropic", "expert", (220_000, 270_000), "Remote (US)", False, 85, 100),
            ("openai", "mixed", (250_000, 300_000), "Austin, TX", False, 75, 95),
            ("parloa", "advanced", (180_000, 220_000), "Remote", False, 60, 85),
            ("deepgram", "expert", (190_000, 240_000), "Onsite (NYC)", False, 55, 80),
            ("liveperson", "none", (200_000, 250_000), "Remote", False, 15, 40),
            ("scale_ai", "expert", (140_000, 160_000), "Remote", False, 40, 65),
            ("google", "mixed", (None, None), "Austin, TX", False, 65, 85),
            ("aws", "expert", (230_000, 280_000), "Remote", False, 80, 100),
            ("soundhound", "expert", (250_000, 300_000), "Remote", True, 0, 0),    # Excluded -> 0
            ("linkedin", "mixed", (190_000, 240_000), "Remote", False, 70, 90),
        ],
    )
    def test_pairwise_scoring_matrix(
        self,
        board: str,
        skill_overlap_kind: str,
        salary_range: tuple[int | None, int | None],
        location: str,
        is_excluded: bool,
        expected_min_score: int,
        expected_max_score: int,
        candidate_profile: CandidateProfile,
    ):
        """Tier 3: Pairwise combination asserting score boundaries and hard gates."""
        skills_map = {
            "expert": ["Conversational AI", "Multi-Agent Systems", "Python", "FastAPI"],
            "advanced": ["Rust", "PyTorch", "Kubernetes & k0s/k3s"],
            "mixed": ["Conversational AI", "Rust", "Python"],
            "none": ["Forklift Operation", "Direct Sales"],
        }
        employer = "SoundHound AI" if is_excluded else f"{board.replace('_', ' ').title()}"
        posting = JobPosting(
            id=f"pairwise-{board}",
            employer=employer,
            title="Enterprise AI Solutions Architect",
            location=location,
            description=f"Job posting on {board}",
            required_skills=skills_map[skill_overlap_kind],
            salary_min=salary_range[0],
            salary_max=salary_range[1],
            salary_currency="USD",
            url=f"https://{board}.com/jobs/test",
            source_board=board,
            posted_at="2026-08-20T10:00:00Z",
        )

        res = compute_profile_match(posting, candidate_profile)
        assert expected_min_score <= res.score <= expected_max_score, (
            f"Failed pairwise test for board={board}, skills={skill_overlap_kind}, comp={salary_range}: "
            f"got score {res.score}, expected [{expected_min_score}, {expected_max_score}]"
        )


# ============================================================================
# TIER 4: REAL-WORLD E2E SCENARIO & CLI JSON FORMATTING
# ============================================================================

class TestDynamicJobSourcingCLIAndE2EScenario:
    """Verifies CLI execution, JSON output formatting, and Scenario S2 pipeline flow."""

    def test_cli_help_displays_all_options(self, capsys):
        """CLI: --help renders cleanly with returncode 0."""
        with pytest.raises(SystemExit) as exc:
            import asyncio
            asyncio.run(sense_jobs_main(["--help"]))
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "--board" in captured.out
        assert "--min-score" in captured.out
        assert "--json" in captured.out

    @pytest.mark.asyncio
    async def test_cli_json_output_schema_and_min_score_filtering(self, capsys):
        """CLI: --json flag outputs valid JSON schema and filters by --min-score."""
        mock_postings = [
            JobPosting(
                id="high-fit",
                employer="Anthropic",
                title="Solutions Architect — Enterprise AI",
                location="Remote",
                description="Conversational AI and multi-agent platforms with Python and FastAPI.",
                required_skills=["Conversational AI", "Multi-Agent Systems", "FastAPI"],
                salary_min=240_000,
                salary_max=280_000,
                salary_currency="USD",
                url="https://anthropic.com/1",
                source_board="anthropic",
                posted_at="2026-08-20T10:00:00Z",
            ),
            JobPosting(
                id="low-fit",
                employer="Other Corp",
                title="Junior Web Content Editor",
                location="Onsite (Miami)",
                description="WordPress blog editor.",
                required_skills=["WordPress", "SEO"],
                salary_min=50_000,
                salary_max=60_000,
                salary_currency="USD",
                url="https://other.com/2",
                source_board="linkedin",
                posted_at="2026-08-20T10:00:00Z",
            ),
        ]

        with patch("cli.sense_jobs.JobSourcingEngine.source_all_boards", new_callable=AsyncMock) as mock_source:
            mock_source.return_value = mock_postings
            exit_code = await sense_jobs_main(["--board", "anthropic", "--min-score", "75", "--json"])
            assert exit_code == 0

            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["employer"] == "Anthropic"
            assert data[0]["match_score"]["score"] >= 75
            assert "breakdown" in data[0]["match_score"]
            assert "risk_flags" in data[0]["match_score"]

    @pytest.mark.asyncio
    async def test_e2e_scenario_s2_dynamic_sourcing_to_lead_ingestion_payload(
        self, candidate_profile: CandidateProfile
    ):
        """Tier 4 / Scenario S2: End-to-end flow from profile-driven sourcing to CRM Lead payload."""
        engine = JobSourcingEngine(candidate_profile=candidate_profile)
        sample_scraped = [
            JobPosting(
                id="parloa-lead-01",
                employer="Parloa",
                title="Head of Solutions Engineering — Agentic Voice AI",
                location="Remote",
                description="Lead solutions architecture for conversational and voice AI platforms.",
                required_skills=["Conversational AI", "Voice AI / ASR / TTS", "Python", "FastAPI"],
                salary_min=240_000,
                salary_max=290_000,
                salary_currency="USD",
                url="https://parloa.com/careers/head-se",
                source_board="parloa",
                posted_at="2026-08-20T10:00:00Z",
            )
        ]

        with patch.object(engine, "_scrape_board", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = sample_scraped
            leads = await engine.source_and_score_leads(min_score=80)

            assert len(leads) == 1
            lead = leads[0]
            assert lead["employer"] == "Parloa"
            assert lead["title"] == "Head of Solutions Engineering — Agentic Voice AI"
            assert lead["score"] >= 85
            assert lead["state"] == "discovered"
            assert lead["source_evidence_kind"] == "career_board_sense"
            assert lead["source_board"] == "parloa"
            assert "breakdown" in lead


# ============================================================================
# REST API ENDPOINT TESTS
# ============================================================================

class TestProfileRestAPI:
    """Verifies FastAPI REST endpoints for /profile and /api/v1/profile."""

    @pytest.fixture
    def client(self, db_session):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        yield TestClient(app)
        app.dependency_overrides.clear()

    def test_get_profile_endpoint(self, client: TestClient):
        """GET /api/v1/profile returns authoritative profile."""
        resp = client.get("/api/v1/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_name"] == "Nate Walker"
        assert len(data["skills"]) >= 40

    def test_get_profile_skills_endpoint(self, client: TestClient):
        """GET /api/v1/profile/skills returns skills breakdown."""
        resp = client.get("/api/v1/profile/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 40
        assert data["expert_count"] >= 15
        assert data["advanced_count"] >= 15

    def test_get_profile_skills_filtered_by_tier(self, client: TestClient):
        """GET /api/v1/profile/skills?tier=expert filters correctly."""
        resp = client.get("/api/v1/profile/skills?tier=expert")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 15
        assert all(s["tier"] == "expert" for s in data["skills"])

    def test_get_profile_ml_depth_endpoint(self, client: TestClient):
        """GET /api/v1/profile/ml-depth returns production ML depth."""
        resp = client.get("/api/v1/profile/ml-depth")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_orchestration" in data
        assert "asr_tts_voice" in data

    def test_get_profile_roles_endpoint(self, client: TestClient):
        """GET /api/v1/profile/roles returns target roles and comp."""
        resp = client.get("/api/v1/profile/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["target_roles"]) >= 4
        assert data["compensation"]["min_base"] == 180000

    def test_put_profile_endpoint(self, client: TestClient):
        """PUT /api/v1/profile updates candidate profile."""
        prof = get_ratified_candidate_profile()
        prof.candidate_name = "Nathaniel Walker"
        resp = client.put("/api/v1/profile", json=json.loads(prof.model_dump_json()))
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_name"] == "Nathaniel Walker"
