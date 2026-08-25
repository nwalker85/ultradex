"""Deterministic, rule-based opportunity scorer v1 (CCC Wave 2, Lane F1).

Per ADR-014 and the Wave 2 implementation plan, scoring is deterministic and
rule-based for v1 — no ML model, no LLM call. It measures one opportunity
against the single workspace Intent record (`IntentProjectionDB`) on four
weighted rules — role family, domain/keyword, seniority band, and
location/remote compatibility — and treats `employer_exclusions` as a hard
gate: an excluded employer always scores 0 and is marked excluded in
`score_explanation`, never ranked alongside genuine candidates.

Weights (`IntentWeightsV1.*_weight`) are integer 0-100 percentages, not
fractional 0-1 floats — that's the contract's native representation
(`_integer(value, label, 0, 100)`), chosen precisely so weights stay
receiptable: `intent.set` commands are receipted via
`core/jobsearch_receipts.py::ReceiptIssuer.issue()`, and
`accountability_v1.canonical_accountability_bytes` rejects any Python float
anywhere in a receipted command or result. Normalization below divides by the
sum of the four weights, so the 0-100 scale is not required to sum to 100 —
any relative integer weighting works the same as it would on a 0-1 scale.

`lens` is accepted only for `OpportunityScorer` protocol / command-schema
compatibility (`opportunities.score` requires it); v1 does not yet use it as
a scoring dimension. A future lens-aware scorer is an explicit later option
per the Wave 2 plan, not part of this rule set.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy.orm import Session

from .jobsearch_executors import (
    DomainRefusal,
    OpportunityScoreResult,
    RelationshipSyncResult,
)
from .jobsearch_models import (
    INTENT_SINGLETON_ID,
    IntentProjectionDB,
    OpportunityProjectionDB,
)


DEFAULT_SCORE_LENS = "default"

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "in",
        "for",
        "with",
        "to",
        "on",
        "at",
        "by",
        "is",
        "are",
        "as",
        "&",
    }
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Known employer name/brand collisions. Resume provenance (Intent seed
# §1.5/§4): "SoundHound AI / Amelia (formerly IPsoft Amelia)" is one employer
# under two brand names used across different sourcing passes. Exclusion
# matching must treat every alias in a group as the same employer even when
# the Intent record's exclusion list only names one spelling — otherwise a
# duplicate-listed opportunity under the other name silently evades the gate.
EMPLOYER_ALIAS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"soundhound ai", "soundhound", "amelia", "ipsoft amelia"}),
)


def _tokens(text: str | None) -> frozenset[str]:
    if not text:
        return frozenset()
    return frozenset(
        word
        for word in _TOKEN_PATTERN.findall(text.lower())
        if word not in _STOPWORDS and len(word) > 1
    )


def _canonical_employer(name: str) -> str:
    normalized = re.sub(r"[.,]", "", name.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    for group in EMPLOYER_ALIAS_GROUPS:
        if normalized in group:
            return "|".join(sorted(group))
    return normalized


def _match_exclusion(
    employer_name: str,
    exclusions: list[dict[str, str]],
) -> dict[str, str] | None:
    canonical_opportunity = _canonical_employer(employer_name)
    for exclusion in exclusions:
        if _canonical_employer(str(exclusion["employer"])) == canonical_opportunity:
            return exclusion
    return None


def _best_overlap_ratio(
    candidate_tokens: frozenset[str],
    targets: list[str],
) -> tuple[float, str | None]:
    best_ratio = 0.0
    best_target: str | None = None
    for target in targets:
        target_tokens = _tokens(target)
        if not target_tokens:
            continue
        ratio = len(candidate_tokens & target_tokens) / len(target_tokens)
        if ratio > best_ratio:
            best_ratio = ratio
            best_target = target
    return best_ratio, best_target


def _domain_match(
    candidate_tokens: frozenset[str],
    domains: list[str],
) -> tuple[float, tuple[str, ...]]:
    matched = tuple(
        domain for domain in domains if _tokens(domain) & candidate_tokens
    )
    ratio = len(matched) / len(domains) if domains else 0.0
    return ratio, matched


def _location_match(
    opportunity_location: str | None,
    remote_preference: str,
    location_preference: str | None,
) -> tuple[float, str]:
    if opportunity_location is None:
        return 0.5, "opportunity location unknown (neutral)"
    location_tokens = _tokens(opportunity_location)
    preference_tokens = _tokens(location_preference)
    if remote_preference in {"remote_only", "remote_first"} and "remote" in location_tokens:
        return 1.0, "remote opportunity matches remote-preferring intent"
    if preference_tokens and (location_tokens & preference_tokens):
        return 1.0, f"opportunity location matches stated preference '{location_preference}'"
    if remote_preference == "flexible":
        return 0.75, "intent is flexible on location"
    return 0.0, "opportunity location does not match intent preference"


@dataclass(frozen=True)
class _RuleOutcome:
    label: str
    weight: int
    ratio: float
    detail: str


def compute_score(
    opportunity: OpportunityProjectionDB,
    intent: IntentProjectionDB,
) -> OpportunityScoreResult:
    """Pure deterministic scoring rule. No I/O — operates on already-loaded rows."""

    exclusions: list[dict[str, str]] = list(intent.employer_exclusions or [])
    exclusion = _match_exclusion(opportunity.employer_name, exclusions)
    if exclusion is not None:
        explanation = (
            f"excluded: employer in exclusions ({exclusion['reason']}) "
            f"— '{opportunity.employer_name}' matches exclusion entry "
            f"'{exclusion['employer']}'"
        )
        return OpportunityScoreResult(
            score=0,
            explanation=explanation[:1000],
            risk_flags=("employer_excluded",),
        )

    weights: dict[str, int] = dict(intent.weights or {})

    role_tokens = _tokens(opportunity.role_family) | _tokens(opportunity.title)
    role_ratio, role_target = _best_overlap_ratio(
        role_tokens,
        list(intent.target_role_families or []),
    )

    domain_tokens = _tokens(opportunity.title) | _tokens(opportunity.employer_name)
    domain_ratio, matched_domains = _domain_match(
        domain_tokens,
        list(intent.target_domains or []),
    )

    seniority_tokens = _tokens(opportunity.title)
    seniority_targets = [intent.seniority_band] if intent.seniority_band else []
    seniority_ratio, _seniority_target = _best_overlap_ratio(
        seniority_tokens,
        seniority_targets,
    )

    location_ratio, location_detail = _location_match(
        opportunity.location,
        intent.remote_preference,
        intent.location_preference,
    )

    rules = (
        _RuleOutcome(
            "role_family",
            int(weights.get("role_family_weight", 0)),
            role_ratio,
            (
                f"best match against '{role_target}'"
                if role_target is not None
                else "no target role family matched"
            ),
        ),
        _RuleOutcome(
            "domain",
            int(weights.get("domain_weight", 0)),
            domain_ratio,
            (
                f"matched domain(s): {', '.join(matched_domains)}"
                if matched_domains
                else "no target domain/keyword matched"
            ),
        ),
        _RuleOutcome(
            "seniority",
            int(weights.get("seniority_weight", 0)),
            seniority_ratio,
            (
                "seniority band overlap found in title"
                if seniority_ratio > 0
                else "no seniority band signal in title"
            ),
        ),
        _RuleOutcome(
            "location",
            int(weights.get("location_weight", 0)),
            location_ratio,
            location_detail,
        ),
    )

    # Weights are integer 0-100 percentages (see module docstring) that need
    # not sum to 100 — dividing by their sum normalizes regardless of scale,
    # same as it would for fractional 0-1 weights. The final score is always
    # a whole-number 0-100 percentage, matching the weight scale it derives
    # from and `OpportunityV1.fit_score`'s receiptable-int convention.
    total_weight = sum(rule.weight for rule in rules)
    weighted_sum = sum(rule.weight * rule.ratio for rule in rules)
    score = round(100 * weighted_sum / total_weight) if total_weight > 0 else 0
    score = max(0, min(100, score))

    explanation = "; ".join(
        f"{rule.label} {'matched' if rule.ratio > 0 else 'no match'} "
        f"({rule.detail}, weight={rule.weight:g})"
        for rule in rules
    )
    if len(explanation) > 1000:
        explanation = explanation[:997] + "..."

    risk_flags = tuple(
        f"{rule.label}_unmatched"
        for rule in rules
        if rule.ratio == 0 and rule.weight > 0
    )

    return OpportunityScoreResult(
        score=score,
        explanation=explanation,
        risk_flags=risk_flags,
    )


class DeterministicIntentScorer:
    """`OpportunityScorer` binding for the executor's `scorer_unbound` seam.

    Loads the opportunity and the singleton Intent row from the shared
    session and delegates to the pure `compute_score` rule. Refuses (via
    `DomainRefusal`) when there is no Intent to score against at all —
    scoring an opportunity against nothing is a fail-closed condition, not a
    0 score. Employer-exclusion matches are a valid scored outcome (score 0,
    receipted explanation), never a refusal.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    async def score(
        self,
        opportunity_id: str,
        lens: str,
    ) -> OpportunityScoreResult:
        opportunity = self._db.get(OpportunityProjectionDB, opportunity_id)
        if opportunity is None:
            raise DomainRefusal("opportunity_not_found")
        intent = self._db.get(IntentProjectionDB, INTENT_SINGLETON_ID)
        if intent is None:
            raise DomainRefusal("intent_not_set")
        return compute_score(opportunity, intent)


class DeterministicRelationshipResolver:
    """`RelationshipResolver` binding for the executor's `relationship_resolver_unbound` seam."""

    def __init__(self, db: Session) -> None:
        self._db = db

    async def sync(
        self,
        opportunity_id: str,
        dex_contact_ref: str,
    ) -> RelationshipSyncResult:
        from core.models import ContactDB
        import uuid

        contact_id = dex_contact_ref.removeprefix("dex-").removeprefix("contact-")
        contact = self._db.get(ContactDB, contact_id)
        opportunity = self._db.get(OpportunityProjectionDB, opportunity_id)

        relevance_score = 50
        summary = f"Contact link for {dex_contact_ref}"
        if contact and opportunity:
            employer = opportunity.employer_name.lower()
            comp = (contact.company or "").lower()
            title = contact.job_title or "Colleague"
            if employer in comp or comp in employer:
                relevance_score = 90
                summary = f"{contact.name} ({title}) at {contact.company}"
            else:
                relevance_score = 60
                summary = f"{contact.name} ({title})"

        return RelationshipSyncResult(
            relationship_id=f"relationship-{uuid.uuid4()}",
            relevance_score=relevance_score,
            relevance_summary=summary,
        )
