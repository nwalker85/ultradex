from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ravenhelm_contracts.jobsearch_v1 import IntentWeightsV1

from core.jobsearch_executors import DomainRefusal
from core.jobsearch_models import IntentProjectionDB, OpportunityProjectionDB
from core.jobsearch_scoring import DeterministicIntentScorer, compute_score


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def _intent(**overrides) -> IntentProjectionDB:
    defaults = dict(
        id="intent-workspace-01",
        target_role_families=[
            "Agentic AI / Platform Architecture",
            "AI GTM / Business Solutions Leadership",
        ],
        target_domains=["AI infrastructure", "Developer tools", "Healthcare"],
        seniority_band="Director-VP / Principal-Staff IC",
        location_preference="Remote or Austin TX",
        remote_preference="remote_first",
        employer_exclusions=[
            {"employer": "Quant", "reason": "former employer"},
            {"employer": "IntelePeer", "reason": "former employer"},
        ],
        weights={
            "role_family_weight": 30,
            "domain_weight": 25,
            "seniority_weight": 20,
            "location_weight": 5,
        },
        narrative=None,
        source_event_id="event-seed",
        source_event_position="JOBSEARCH:seed",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return IntentProjectionDB(**defaults)


def _opportunity(**overrides) -> OpportunityProjectionDB:
    defaults = dict(
        id="opportunity-01",
        employer_name="UiPath",
        title="Enterprise AI Automation GTM Director",
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


def test_employer_exclusion_is_a_hard_gate_never_ranked():
    intent = _intent()
    opportunity = _opportunity(employer_name="Quant", title="VP Agentic AI Platform")

    result = compute_score(opportunity, intent)

    assert result.score == 0
    assert "excluded: employer in exclusions" in result.explanation
    assert "former employer" in result.explanation
    assert "employer_excluded" in result.risk_flags


def test_exclusion_matching_is_case_and_whitespace_insensitive():
    intent = _intent(
        employer_exclusions=[{"employer": "  intelepeer ", "reason": "current employer"}]
    )
    opportunity = _opportunity(employer_name="IntelePeer")

    result = compute_score(opportunity, intent)

    assert result.score == 0
    assert "excluded" in result.explanation


def test_exclusion_matching_is_robust_to_soundhound_amelia_naming_split():
    """The scorer must not miss an alias even when only one spelling of the
    same employer appears in the Intent's exclusion list — this is the exact
    naming-collision risk the Intent seed doc (§2, §4) flags: SoundHound AI
    and Amelia are one employer, and duplicate-seeded rows under either name
    must both be caught by a single exclusion entry."""
    intent_excludes_amelia_only = _intent(
        employer_exclusions=[{"employer": "Amelia", "reason": "former employer"}]
    )
    soundhound_opportunity = _opportunity(
        employer_name="SoundHound AI",
        title="Senior/Staff AI Platform",
    )

    result = compute_score(soundhound_opportunity, intent_excludes_amelia_only)

    assert result.score == 0
    assert "excluded" in result.explanation

    intent_excludes_soundhound_only = _intent(
        employer_exclusions=[{"employer": "SoundHound AI", "reason": "former employer"}]
    )
    amelia_opportunity = _opportunity(
        employer_name="Amelia",
        title="Conversational/Agentic AI leadership",
    )

    reverse_result = compute_score(amelia_opportunity, intent_excludes_soundhound_only)

    assert reverse_result.score == 0
    assert "excluded" in reverse_result.explanation


def test_non_excluded_employer_scores_and_names_matched_rules():
    intent = _intent()
    opportunity = _opportunity(
        employer_name="UiPath",
        title="Enterprise AI GTM Business Solutions Leadership",
    )

    result = compute_score(opportunity, intent)

    assert result.score > 0
    assert "excluded" not in result.explanation
    assert "role_family matched" in result.explanation
    assert "domain matched" in result.explanation


def test_unmatched_opportunity_scores_zero_with_named_misses():
    # location_weight=0 isolates this case: an unset opportunity.location is
    # scored as neutral (0.5), not a miss, so leaving location_weight nonzero
    # would smuggle a small positive score into an otherwise all-miss case.
    intent = _intent(
        weights={
            "role_family_weight": 30,
            "domain_weight": 25,
            "seniority_weight": 20,
            "location_weight": 0,
        }
    )
    opportunity = _opportunity(
        employer_name="Totally Unrelated Co",
        title="Assistant Store Manager",
    )

    result = compute_score(opportunity, intent)

    assert result.score == 0
    assert "no target role family matched" in result.explanation
    assert "no target domain/keyword matched" in result.explanation
    assert "role_family_unmatched" in result.risk_flags
    assert "domain_unmatched" in result.risk_flags


def test_location_unknown_is_neutral_not_a_penalty():
    intent = _intent(
        weights={
            "role_family_weight": 0,
            "domain_weight": 0,
            "seniority_weight": 0,
            "location_weight": 100,
        }
    )
    opportunity = _opportunity(location=None)

    result = compute_score(opportunity, intent)

    assert result.score == 50
    assert "opportunity location unknown (neutral)" in result.explanation


def test_remote_location_matches_remote_first_preference():
    intent = _intent(
        remote_preference="remote_first",
        weights={
            "role_family_weight": 0,
            "domain_weight": 0,
            "seniority_weight": 0,
            "location_weight": 100,
        },
    )
    opportunity = _opportunity(location="Remote (US)")

    result = compute_score(opportunity, intent)

    assert result.score == 100


def test_intent_weights_reject_fractional_values_at_the_contract_boundary():
    """Weights are integer 0-100 percentages, not fractional 0-1 floats —
    `IntentWeightsV1.from_dict` enforces this (`_integer()`, jobsearch_v1.py),
    specifically because every `intent.set` command is receipted and
    `accountability_v1.canonical_accountability_bytes` rejects any float
    anywhere in a receipted payload. This asserts the contract rejects a
    fractional weight outright, including whole-number-valued floats like
    45.0 — `compute_score()` itself never sees a float weight because nothing
    upstream of it can construct one."""
    valid = {
        "role_family_weight": 30,
        "domain_weight": 25,
        "seniority_weight": 20,
        "location_weight": 5,
    }
    assert IntentWeightsV1.from_dict(valid).role_family_weight == 30

    with pytest.raises(ValueError):
        IntentWeightsV1.from_dict({**valid, "role_family_weight": 0.3})

    with pytest.raises(ValueError):
        # Whole-number-valued floats are rejected too, not just fractions.
        IntentWeightsV1.from_dict({**valid, "role_family_weight": 45.0})


def test_score_is_bounded_and_explanation_within_contract_maximum():
    intent = _intent()
    opportunity = _opportunity(employer_name="UiPath", title="Enterprise AI GTM")

    result = compute_score(opportunity, intent)

    assert 0 <= result.score <= 100
    assert len(result.explanation) <= 1000


@pytest.mark.asyncio
async def test_scorer_refuses_when_intent_is_not_set(db_session):
    opportunity = _opportunity()
    db_session.add(opportunity)
    db_session.commit()
    scorer = DeterministicIntentScorer(db_session)

    with pytest.raises(DomainRefusal) as excinfo:
        await scorer.score(opportunity.id, "default")

    assert excinfo.value.reason_code == "intent_not_set"


@pytest.mark.asyncio
async def test_scorer_refuses_for_unknown_opportunity(db_session):
    db_session.add(_intent())
    db_session.commit()
    scorer = DeterministicIntentScorer(db_session)

    with pytest.raises(DomainRefusal) as excinfo:
        await scorer.score("opportunity-missing", "default")

    assert excinfo.value.reason_code == "opportunity_not_found"


@pytest.mark.asyncio
async def test_scorer_loads_rows_and_delegates_to_compute_score(db_session):
    db_session.add(_intent())
    db_session.add(_opportunity(employer_name="UiPath", title="Enterprise AI GTM"))
    db_session.commit()
    scorer = DeterministicIntentScorer(db_session)

    result = await scorer.score("opportunity-01", "default")

    assert result.score > 0
    assert "excluded" not in result.explanation
