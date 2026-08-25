"""CCC Wave 2 Lane F1: Intent plane projection, `intent.set` executor, and
scorer-v1 wiring (auto-score at opportunity creation, rescore-all on
`intent.set`)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, create_engine

from core.jobsearch_commands import (
    JobSearchCommandRequest,
    JobSearchGatewayService,
)
from core.jobsearch_executors import JobSearchExecutor
from core.jobsearch_migrations import run_jobsearch_migrations
from core.jobsearch_models import (
    INTENT_SINGLETON_ID,
    IntentProjectionDB,
    JobSearchEvidenceReferenceDB,
    OpportunityProjectionDB,
    ProjectionCheckpointDB,
    WORKSPACE_SINGLETON_ID,
)
from core.jobsearch_projections import JobSearchProjectionRepository
from core.jobsearch_scoring import DeterministicIntentScorer


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
COMMITMENT = f"sha256:{'a' * 64}"


async def _accepted(db, publisher, issuer, command, parameters, key):
    await JobSearchGatewayService(publisher, issuer).submit_command(
        db,
        JobSearchCommandRequest(
            command=command,
            parameters=parameters,
            actor_id="operator:test",
            idempotency_key=key,
        ),
    )
    return publisher.commands[-1]


def _ratified_intent_parameters(**overrides) -> dict[str, object]:
    """Nate's ratified Intent seed (CCC Wave 2, INTENT-SEED-DRAFT §4).

    Exclusions cover both spellings of the SoundHound AI / Amelia employer
    plus Quant and IntelePeer, per: "im not at intelepeer anymore... 180 base,
    250 target. prefer remote or Austin TX. Amelia = SoundHound. No Quant,
    Amelia, SoundHound, Intelepeer."

    Weights are integer 0-100 percentages (`IntentWeightsV1`'s native
    representation, enforced by `_integer()` in ravenhelm-contracts —
    fractional weights are rejected at the contract boundary specifically
    because every `intent.set` command is receipted, and the accountability
    receipt layer rejects any float anywhere in a receipted payload; see
    `tests/test_jobsearch_scoring.py::test_intent_weights_reject_fractional_values_at_the_contract_boundary`).
    40/30/20/10 here mirrors INTENT-SEED-DRAFT §1.6's suggested relative
    emphasis (role family highest, then domain, then seniority, location
    lowest) on the contract's actual integer scale.
    """
    parameters: dict[str, object] = {
        "target_role_families": [
            "Enterprise AI Solutions Engineering / Solution Architecture",
            "Agentic AI / Platform Architecture",
            "AI GTM / Business Solutions Leadership",
            "Conversational / Voice AI Enterprise Leadership",
        ],
        "target_domains": [
            "AI infrastructure",
            "Developer tools",
            "Voice and customer experience",
            "Healthcare",
            "Regulated security constrained systems",
            "Agentic AI multi-agent orchestration",
        ],
        "seniority_band": "Director-VP / Principal-Staff IC dual-track",
        "location_preference": "Remote preferred, or Austin TX",
        "remote_preference": "remote_first",
        "employer_exclusions": [
            {"employer": "Quant", "reason": "former employer"},
            {"employer": "Amelia", "reason": "former employer (SoundHound AI / Amelia)"},
            {"employer": "SoundHound AI", "reason": "former employer (SoundHound AI / Amelia)"},
            {"employer": "IntelePeer", "reason": "former employer"},
        ],
        "weights": {
            "role_family_weight": 40,
            "domain_weight": 30,
            "seniority_weight": 20,
            "location_weight": 10,
        },
        "narrative": "Ratified 2026-08-16 per Nate's verbatim rulings.",
    }
    parameters.update(overrides)
    return parameters


def _opportunity_row(**overrides) -> OpportunityProjectionDB:
    defaults = dict(
        id="opportunity-01",
        employer_name="Example",
        title="Platform Engineer",
        location=None,
        role_family=None,
        state="discovered",
        score=None,
        score_explanation=None,
        risk_flags=[],
        evidence_refs=[],
        source_event_id="event-seed",
        source_event_position="JOBSEARCH:seed",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return OpportunityProjectionDB(**defaults)


def test_migration_creates_jobsearch_intent_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'intent-migration.db'}")
    run_jobsearch_migrations(str(engine.url))

    columns = {
        column["name"]
        for column in inspect(engine).get_columns("jobsearch_intent")
    }

    assert {
        "id",
        "target_role_families",
        "target_domains",
        "seniority_band",
        "location_preference",
        "remote_preference",
        "employer_exclusions",
        "weights",
        "narrative",
        "source_event_id",
        "source_event_position",
        "projected_at",
        "created_at",
        "updated_at",
    } <= columns


@pytest.mark.asyncio
async def test_intent_set_creates_singleton_and_is_readable_via_repository(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "intent.set",
        _ratified_intent_parameters(),
        "intent-set-01",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)

    assert outcome.receipt.status == "succeeded"
    row = db_session.get(IntentProjectionDB, INTENT_SINGLETON_ID)
    assert row is not None
    assert row.remote_preference == "remote_first"
    assert len(row.employer_exclusions) == 4

    repository = JobSearchProjectionRepository(db_session)
    intent = repository.get_intent()
    assert intent is not None
    assert intent.intent_id == INTENT_SINGLETON_ID
    assert intent.seniority_band == "Director-VP / Principal-Staff IC dual-track"
    assert intent.freshness.source_event_id == outcome.event.control_surface_event.id


def test_get_intent_returns_none_before_any_intent_set(db_session):
    assert JobSearchProjectionRepository(db_session).get_intent() is None


@pytest.mark.asyncio
async def test_intent_set_is_replace_style_singleton_not_append(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    executor = JobSearchExecutor(db_session, receipt_issuer)
    first = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "intent.set",
            _ratified_intent_parameters(),
            "intent-set-first",
        )
    )
    second = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "intent.set",
            _ratified_intent_parameters(remote_preference="onsite"),
            "intent-set-second",
        )
    )

    assert first.result["intent_id"] == second.result["intent_id"]
    assert (
        db_session.query(IntentProjectionDB).count() == 1
    ), "intent.set must overwrite the singleton row, never append a new one"
    row = db_session.get(IntentProjectionDB, INTENT_SINGLETON_ID)
    assert row.remote_preference == "onsite"


@pytest.mark.asyncio
async def test_intent_set_rescores_every_existing_opportunity(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    db_session.add_all(
        [
            _opportunity_row(
                id="opportunity-uipath",
                employer_name="UiPath",
                title="Enterprise AI GTM Business Solutions Leadership",
            ),
            _opportunity_row(
                id="opportunity-quant",
                employer_name="Quant",
                title="VP Agentic AI Platform Business Solutions",
            ),
        ]
    )
    db_session.commit()
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        scorer=DeterministicIntentScorer(db_session),
    )

    outcome = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "intent.set",
            _ratified_intent_parameters(),
            "intent-set-rescore",
        )
    )

    assert outcome.result["rescored_count"] == 2
    uipath = db_session.get(OpportunityProjectionDB, "opportunity-uipath")
    quant = db_session.get(OpportunityProjectionDB, "opportunity-quant")
    assert uipath.score is not None and uipath.score > 0
    assert "excluded" not in uipath.score_explanation
    assert quant.score == 0
    assert "excluded" in quant.score_explanation
    assert uipath.source_event_id == outcome.event.control_surface_event.id
    assert quant.source_event_id == outcome.event.control_surface_event.id
    checkpoint = db_session.get(ProjectionCheckpointDB, "intent")
    assert checkpoint is not None
    assert checkpoint.status == "fresh"


@pytest.mark.asyncio
async def test_intent_set_without_bound_scorer_still_succeeds(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    db_session.add(_opportunity_row())
    db_session.commit()
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "intent.set",
            _ratified_intent_parameters(),
            "intent-set-no-scorer",
        )
    )

    assert outcome.receipt.status == "succeeded"
    assert outcome.result["rescored_count"] == 0
    opportunity = db_session.get(OpportunityProjectionDB, "opportunity-01")
    assert opportunity.score is None


@pytest.mark.asyncio
async def test_opportunity_create_is_not_scored_when_no_intent_exists(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    db_session.add(
        JobSearchEvidenceReferenceDB(
            evidence_id="evidence-01",
            source_kind="web",
            source_ref="web-source-01",
            classification="private",
            observed_at=NOW,
            commitment=COMMITMENT,
            redacted_summary="Public role metadata reviewed.",
            created_at=NOW,
        )
    )
    db_session.commit()
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        scorer=DeterministicIntentScorer(db_session),
    )

    outcome = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "opportunities.create",
            {
                "employer": "UiPath",
                "title": "Enterprise AI GTM",
                "source_evidence_id": "evidence-01",
            },
            "create-no-intent",
        )
    )

    row = db_session.get(
        OpportunityProjectionDB,
        outcome.result["opportunity_id"],
    )
    assert row.score is None
    assert row.state == "discovered"


@pytest.mark.asyncio
async def test_opportunity_create_is_scored_at_creation_when_intent_exists(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    db_session.add(
        JobSearchEvidenceReferenceDB(
            evidence_id="evidence-01",
            source_kind="web",
            source_ref="web-source-01",
            classification="private",
            observed_at=NOW,
            commitment=COMMITMENT,
            redacted_summary="Public role metadata reviewed.",
            created_at=NOW,
        )
    )
    db_session.commit()
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        scorer=DeterministicIntentScorer(db_session),
    )
    await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "intent.set",
            _ratified_intent_parameters(),
            "intent-set-before-create",
        )
    )

    outcome = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "opportunities.create",
            {
                "employer": "UiPath",
                "title": "Enterprise AI GTM",
                "source_evidence_id": "evidence-01",
            },
            "create-with-intent",
        )
    )

    row = db_session.get(
        OpportunityProjectionDB,
        outcome.result["opportunity_id"],
    )
    assert row.score is not None
    assert row.score > 0
    assert "excluded" not in row.score_explanation


@pytest.mark.asyncio
async def test_opportunity_create_scores_excluded_employer_zero_not_refused(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    db_session.add(
        JobSearchEvidenceReferenceDB(
            evidence_id="evidence-01",
            source_kind="web",
            source_ref="web-source-01",
            classification="private",
            observed_at=NOW,
            commitment=COMMITMENT,
            redacted_summary="Public role metadata reviewed.",
            created_at=NOW,
        )
    )
    db_session.commit()
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        scorer=DeterministicIntentScorer(db_session),
    )
    await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "intent.set",
            _ratified_intent_parameters(),
            "intent-set-before-create-excluded",
        )
    )

    outcome = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "opportunities.create",
            {
                "employer": "IntelePeer",
                "title": "AI Customer Outcomes and CX",
                "source_evidence_id": "evidence-01",
            },
            "create-excluded",
        )
    )

    assert outcome.receipt.status == "succeeded"
    row = db_session.get(
        OpportunityProjectionDB,
        outcome.result["opportunity_id"],
    )
    assert row.score == 0
    assert "excluded" in row.score_explanation


@pytest.mark.asyncio
async def test_workspace_initialize_is_idempotent(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    executor = JobSearchExecutor(db_session, receipt_issuer)
    first = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "workspace.initialize",
            {},
            "workspace-init-01",
        )
    )
    second = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "workspace.initialize",
            {},
            "workspace-init-02",
        )
    )

    assert first.receipt.status == "succeeded"
    assert second.receipt.status == "succeeded"
    assert first.result["workspace_id"] == WORKSPACE_SINGLETON_ID
    assert second.result["workspace_id"] == WORKSPACE_SINGLETON_ID


@pytest.mark.asyncio
async def test_applications_create_and_outreach_cancel_refuse_when_entities_missing(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    """Lane F2 is integrated on this branch: missing entities refuse with
    the real domain codes, not the pre-F2 catalog stubs."""
    executor = JobSearchExecutor(db_session, receipt_issuer)

    create_outcome = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "applications.create",
            {"opportunity_id": "opportunity-01", "occurred_at": "2026-08-16T12:00:00Z"},
            "applications-create-stub",
        )
    )
    cancel_outcome = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "outreach.cancel",
            {"outreach_id": "outreach-01", "reason": "window lapsed"},
            "outreach-cancel-stub",
        )
    )

    assert create_outcome.receipt.status == "refused"
    assert create_outcome.result["reason_code"] == "opportunity_not_found"
    assert cancel_outcome.receipt.status == "refused"
    assert cancel_outcome.result["reason_code"] == "outreach_not_found"


@pytest.mark.asyncio
async def test_calibration_only_uipath_is_rankable_among_five_seeded_employers(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    """Reproduces the live-database finding that triggered CCC Wave 2: of the
    five seeded employers (SoundHound AI, Amelia, Quant, UiPath, IntelePeer),
    only UiPath should receive a rankable score once Nate's ratified Intent
    (INTENT-SEED-DRAFT §4) is set — the other four are former/current
    employers and must be excluded with an explanation naming the
    exclusion."""
    seeded = [
        _opportunity_row(
            id="opportunity-soundhound",
            employer_name="SoundHound AI",
            title="Senior/Staff AI Platform",
        ),
        _opportunity_row(
            id="opportunity-amelia",
            employer_name="Amelia",
            title="Conversational Agentic AI Leadership",
        ),
        _opportunity_row(
            id="opportunity-quant",
            employer_name="Quant",
            title="Agentic AI Implementation Platform",
        ),
        _opportunity_row(
            id="opportunity-uipath",
            employer_name="UiPath",
            title="Enterprise AI Automation GTM",
        ),
        _opportunity_row(
            id="opportunity-intelepeer",
            employer_name="IntelePeer",
            title="AI Customer Outcomes and CX",
        ),
    ]
    db_session.add_all(seeded)
    db_session.commit()
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        scorer=DeterministicIntentScorer(db_session),
    )

    outcome = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "intent.set",
            _ratified_intent_parameters(),
            "intent-set-calibration",
        )
    )
    assert outcome.result["rescored_count"] == 5

    excluded_ids = {
        "opportunity-soundhound",
        "opportunity-amelia",
        "opportunity-quant",
        "opportunity-intelepeer",
    }
    for opportunity_id in excluded_ids:
        row = db_session.get(OpportunityProjectionDB, opportunity_id)
        assert row.score == 0, f"{opportunity_id} should be excluded (score 0)"
        assert "excluded: employer in exclusions" in row.score_explanation
        assert "employer_excluded" in row.risk_flags

    uipath = db_session.get(OpportunityProjectionDB, "opportunity-uipath")
    assert uipath.score is not None and uipath.score > 0
    assert "excluded" not in uipath.score_explanation
