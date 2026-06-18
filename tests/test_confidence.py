from app.schemas.marksheet import (
    CandidateDetails, FieldValue, MarksheetExtraction, NumericFieldValue, OverallResult, SubjectMark,
)
from app.services.confidence import merge_and_score


def _candidate(name="Sumit Kumar", roll="0416173", board="UP Board"):
    return CandidateDetails(
        name=FieldValue(value=name, confidence=0.95),
        roll_no=FieldValue(value=roll, confidence=0.9),
        board_or_university=FieldValue(value=board, confidence=0.9),
    )


def _subject(name="MATHEMATICS", marks=85.0, confidence=0.9):
    return SubjectMark(
        subject_name=FieldValue(value=name, confidence=confidence),
        obtained_marks=NumericFieldValue(value=marks, confidence=confidence),
    )


def test_agreement_boosts_confidence():
    candidate = _candidate()
    first = MarksheetExtraction(candidate=candidate, subjects=[_subject()], result=OverallResult(), document_confidence=0.0)
    second = MarksheetExtraction(candidate=candidate.model_copy(deep=True), subjects=[_subject()], result=OverallResult(), document_confidence=0.0)

    merged = merge_and_score(first, second)

    assert merged.candidate.name.value == "Sumit Kumar"
    assert merged.candidate.name.confidence > 0.95
    assert merged.warnings == []


def test_disagreement_lowers_confidence_and_warns():
    first = MarksheetExtraction(candidate=_candidate(name="Sumit Kumar"), subjects=[], result=OverallResult(), document_confidence=0.0)
    second = MarksheetExtraction(candidate=_candidate(name="Sumlt Kumar"), subjects=[], result=OverallResult(), document_confidence=0.0)

    merged = merge_and_score(first, second)

    assert merged.candidate.name.confidence < 0.95
    assert any("candidate.name" in w for w in merged.warnings)


def test_subject_found_in_only_one_pass_gets_penalized():
    first = MarksheetExtraction(
        candidate=_candidate(), subjects=[_subject("MATHEMATICS"), _subject("SCIENCE")],
        result=OverallResult(), document_confidence=0.0,
    )
    second = MarksheetExtraction(candidate=_candidate(), subjects=[_subject("MATHEMATICS")], result=OverallResult(), document_confidence=0.0)

    merged = merge_and_score(first, second)

    science = next(s for s in merged.subjects if s.subject_name.value == "SCIENCE")
    assert science.obtained_marks.confidence < 0.9
    assert any("different counts" in w for w in merged.warnings)


def test_missing_required_field_drops_confidence_to_zero():
    candidate = CandidateDetails(
        name=FieldValue(value=None, confidence=0.3),
        roll_no=FieldValue(value="0416173", confidence=0.9),
        board_or_university=FieldValue(value="UP Board", confidence=0.9),
    )
    first = MarksheetExtraction(candidate=candidate, subjects=[], result=OverallResult(), document_confidence=0.0)
    second = MarksheetExtraction(candidate=candidate.model_copy(deep=True), subjects=[], result=OverallResult(), document_confidence=0.0)

    merged = merge_and_score(first, second)

    assert merged.candidate.name.confidence == 0.0
    assert any("required field candidate.name" in w for w in merged.warnings)


def test_marks_sum_mismatch_flags_total():
    subjects = [_subject("MATHEMATICS", marks=85.0), _subject("SCIENCE", marks=73.0)]
    result = OverallResult(total_obtained_marks=NumericFieldValue(value=999.0, confidence=0.9))

    first = MarksheetExtraction(candidate=_candidate(), subjects=subjects, result=result, document_confidence=0.0)
    second = MarksheetExtraction(
        candidate=_candidate(), subjects=[s.model_copy(deep=True) for s in subjects],
        result=result.model_copy(deep=True), document_confidence=0.0,
    )

    merged = merge_and_score(first, second)

    assert any("does not match the printed total" in w for w in merged.warnings)