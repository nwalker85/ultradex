"""Tests for Sovereign Voice, Gjallarhorn ASR & Obsidian Exporter (Milestone M3, Feature F9)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest
import httpx

from core.jobsearch_copilot import ActionType, ActionUrgency
from core.jobsearch_gjallarhorn import (
    FitAssessment,
    GjallarhornASRClient,
    GjallarhornMQTTListener,
    InterviewActionItem,
    InterviewDebrief,
    InterviewDebriefExtractor,
    InterviewMetadata,
    QuestionAnswerPair,
    SpeakerRole,
    TranscriptSegment,
    export_debrief_to_obsidian,
    extract_interview_debrief,
    inject_debrief_actions_to_copilot,
    sanitize_filename_segment,
)


def test_gjallarhorn_asr_client_transcribe() -> None:
    mock_payload = {
        "segments": [
            {"start": 0.5, "speaker": "Sarah Chen", "text": "Hi Nate, thanks for taking the time.", "confidence": 0.98},
            {"start": 3.2, "speaker": "Nate Walker", "text": "Great to meet you Sarah, excited to discuss the role.", "confidence": 0.99},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://ratatoskr:18099/asr"
        return httpx.Response(200, json=mock_payload)

    client = GjallarhornASRClient(endpoint_url="http://ratatoskr:18099/asr")
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_http:
        segments = client.transcribe_audio(
            audio_bytes=b"RIFFmockwavdata",
            filename="interview.wav",
            client=mock_http,
        )

    assert len(segments) == 2
    assert segments[0].speaker == "Sarah Chen"
    assert segments[0].role == SpeakerRole.INTERVIEWER
    assert segments[0].offset_ms == 500

    assert segments[1].speaker == "Nate Walker"
    assert segments[1].role == SpeakerRole.CANDIDATE
    assert segments[1].offset_ms == 3200


def test_gjallarhorn_asr_client_handles_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = GjallarhornASRClient()
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_http:
        with pytest.raises(RuntimeError) as exc:
            client.transcribe_audio(audio_bytes=b"dummy", client=mock_http)
        assert "Gjallarhorn ASR failed with HTTP 500" in str(exc.value)


def test_mqtt_listener_transcript_accumulation() -> None:
    listener = GjallarhornMQTTListener()

    chunk1 = json_str = '{"offset_ms": 1000, "speaker": "Alex", "text": "Can you describe your experience with MCP?"}'
    chunk2 = '[{"offset_ms": 5000, "speaker": "Nate", "text": "I built custom MCP tool gateways connecting multi-agent systems."}]'

    listener.accumulate_chunk("gjallarhorn/interview/transcript", chunk1)
    listener.accumulate_chunk("gjallarhorn/interview/transcript", chunk2)

    text = listener.get_transcript_text()
    assert "[00:01] **Alex**: Can you describe your experience with MCP?" in text
    assert "[00:05] **Nate**: I built custom MCP tool gateways connecting multi-agent systems." in text


def test_extract_interview_debrief_structured() -> None:
    transcript = (
        "[00:01] **Sarah Chen**: Hi Nate, how do you handle zero-downtime database migrations on high-scale distributed systems?\n"
        "[00:15] **Nate Walker**: We implement expand-contract schema patterns using Alembic, dual-writing data with shadow reads in PostgreSQL before migrating.\n"
        "[00:45] **Sarah Chen**: How do you architect Kubernetes clusters for sovereign voice and LLM inference?\n"
        "[01:00] **Nate Walker**: We deploy on K8s using GPU node pools with FastAPI backends, streaming audio over NATS and Whisper ASR models.\n"
    )
    meta = InterviewMetadata(
        company="Anthropic",
        role="Principal AI Architect",
        round_type="Technical Deep Dive",
        interview_date="2026-08-25",
        interviewer_names=["Sarah Chen"],
        interviewer_titles=["Director of AI Engineering"],
        duration_minutes=45,
        opportunity_id="opp-anthropic-101",
    )

    debrief = extract_interview_debrief(transcript=transcript, metadata=meta)

    assert debrief.metadata.company == "Anthropic"
    assert "Anthropic" in debrief.executive_summary
    assert len(debrief.questions_and_answers) == 2

    qa1 = debrief.questions_and_answers[0]
    assert "zero-downtime database migrations" in qa1.question
    assert "Alembic" in qa1.key_points_mentioned
    assert "PostgreSQL" in qa1.key_points_mentioned

    qa2 = debrief.questions_and_answers[1]
    assert "Kubernetes clusters" in qa2.question
    assert "FastAPI" in qa2.key_points_mentioned or "Kubernetes" in qa2.key_points_mentioned

    # Fit assessment
    assert debrief.fit_assessment.overall_score >= 90.0
    assert len(debrief.fit_assessment.green_flags) >= 1
    assert len(debrief.fit_assessment.red_flags) == 0

    # Action items
    assert len(debrief.action_items) == 2
    act_ty = next(a for a in debrief.action_items if a.action_type == "thank_you_note")
    assert act_ty.priority == "p0"
    assert act_ty.due_date == "2026-08-26"
    assert "Sarah Chen" in act_ty.title


def test_extract_interview_debrief_flags_red_flag_comp() -> None:
    transcript = (
        "[00:01] **Recruiter**: Hi Nate, our compensation band for this role is capped at $150k base.\n"
        "[00:20] **Nate Walker**: My target is $180k+ base given my executive engineering background.\n"
    )
    meta = InterviewMetadata(
        company="BudgetAI",
        role="Head of AI",
        interview_date="2026-08-25",
        interviewer_names=["Recruiter"],
    )

    debrief = extract_interview_debrief(transcript=transcript, metadata=meta)
    assert len(debrief.fit_assessment.red_flags) >= 1
    assert any("below candidate minimum expectation" in rf for rf in debrief.fit_assessment.red_flags)


def test_debrief_action_items_copilot_injection() -> None:
    meta = InterviewMetadata(
        company="OpenAI",
        role="Principal Systems Architect",
        round_type="System Design",
        interview_date="2026-08-25",
        interviewer_names=["Greg Brockman"],
        opportunity_id="opp-openai-99",
    )
    debrief = InterviewDebrief(
        metadata=meta,
        executive_summary="Deep dive into inference engines.",
        fit_assessment=FitAssessment(
            technical_alignment="High",
            leadership_alignment="High",
            compensation_alignment="High",
        ),
        action_items=[
            InterviewActionItem(
                id="act-greg-ty",
                title="Send Thank-You Note to Greg Brockman (OpenAI)",
                action_type="thank_you_note",
                priority="p0",
                due_date="2026-08-26",
                recipient_name="Greg Brockman",
                draft_content="Hi Greg, great speaking today...",
                opportunity_id="opp-openai-99",
                is_completed=False,
            )
        ],
    )

    actions = inject_debrief_actions_to_copilot(debrief)
    assert len(actions) == 1
    act = actions[0]
    assert act.urgency == ActionUrgency.P0
    assert act.action_type == ActionType.SEND_THANK_YOU
    assert act.entity_id == "opp-openai-99"
    assert act.action_url == "/opportunities/opp-openai-99"
    assert act.score == 95.0


def test_obsidian_exporter_writes_valid_markdown(tmp_path: Path) -> None:
    meta = InterviewMetadata(
        company="Anthropic",
        role="Principal AI Architect",
        round_type="Technical Deep Dive",
        interview_date="2026-08-25",
        interviewer_names=["Sarah Chen", "Dario Amodei"],
        opportunity_id="opp-anthropic-1",
    )
    debrief = InterviewDebrief(
        metadata=meta,
        executive_summary="Exceptional alignment on multi-agent MCP orchestration.",
        questions_and_answers=[
            QuestionAnswerPair(
                id="qa-1",
                question="How do you handle tool authorization in agent loops?",
                asked_by="Sarah Chen",
                category="Security & Agent Governance",
                answer_summary="Described cryptographic capability grants and human-in-the-loop gates.",
                key_points_mentioned=["MCP", "Security", "FastAPI"],
                effectiveness_score=9.8,
            )
        ],
        fit_assessment=FitAssessment(
            overall_score=94.0,
            technical_alignment="Full overlap with Python, K8s, and MCP.",
            leadership_alignment="Strong pragmatic resonance.",
            compensation_alignment="Aligned with $180k/$250k bounds.",
            green_flags=["High engineering rigor"],
            red_flags=[],
        ),
        action_items=[
            InterviewActionItem(
                id="act-1",
                title="Send Thank-You Note to Sarah Chen",
                action_type="thank_you_note",
                priority="p0",
                due_date="2026-08-26",
            )
        ],
        raw_transcript="[00:00] **Sarah**: Welcome Nate...",
    )

    out_file = export_debrief_to_obsidian(debrief=debrief, vault_dir=tmp_path)

    assert out_file.exists()
    assert out_file.name == "2026-08-25_anthropic_principal_ai_architect_debrief.md"

    content = out_file.read_text(encoding="utf-8")
    assert "title: \"Interview Debrief: Anthropic — Principal AI Architect\"" in content
    assert "fit_score: 94.0" in content
    assert "## Executive Summary" in content
    assert "## Questions Asked & Answers Given" in content
    assert "### 1. How do you handle tool authorization in agent loops?" in content
    assert "## Technical & Culture Fit Assessment" in content
    assert "## Action Items & Next Steps" in content
    assert "- [ ] **P0 (Due 2026-08-26)**: Send Thank-You Note to Sarah Chen" in content
    assert "## Raw Transcript" in content


def test_obsidian_exporter_filename_sanitization(tmp_path: Path) -> None:
    assert sanitize_filename_segment("Scale AI / Labs & Co.") == "scale_ai_labs_co"
    assert sanitize_filename_segment("VP of Eng / CTO — Platform") == "vp_of_eng_cto_platform"


def test_obsidian_exporter_idempotent_atomic_overwrite(tmp_path: Path) -> None:
    meta = InterviewMetadata(
        company="Deepgram",
        role="Head of Voice AI",
        interview_date="2026-08-25",
        interviewer_names=["Scott Stephenson"],
    )
    debrief = InterviewDebrief(
        metadata=meta,
        executive_summary="Initial debrief summary.",
        fit_assessment=FitAssessment(
            technical_alignment="Voice ASR/TTS",
            leadership_alignment="Executive",
            compensation_alignment="Aligned",
        ),
        action_items=[],
    )

    f1 = export_debrief_to_obsidian(debrief=debrief, vault_dir=tmp_path)
    assert f1.exists()
    content1 = f1.read_text(encoding="utf-8")
    assert "Initial debrief summary." in content1

    # Update summary and re-export
    debrief.executive_summary = "Updated debrief summary with post-meeting thoughts."
    f2 = export_debrief_to_obsidian(debrief=debrief, vault_dir=tmp_path)
    assert f1 == f2
    content2 = f2.read_text(encoding="utf-8")
    assert "Updated debrief summary with post-meeting thoughts." in content2

    # Verify no tmp files lingering
    tmp_files = list(tmp_path.glob(".tmp_*"))
    assert len(tmp_files) == 0
