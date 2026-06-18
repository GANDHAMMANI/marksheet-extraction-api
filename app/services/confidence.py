from typing import Optional

from app.schemas.marksheet import (
    CandidateDetails, FieldValue, IssueInfo, MarksheetExtraction,
    NumericFieldValue, OverallResult, SubjectMark,
)

AGREEMENT_BOOST = 0.05
DISAGREEMENT_PENALTY = 0.5
REQUIRED_CANDIDATE_FIELDS = ["name", "roll_no", "board_or_university"]


def merge_and_score(first: MarksheetExtraction, second: MarksheetExtraction) -> MarksheetExtraction:
    warnings: list[str] = []

    candidate = _merge_candidate(first.candidate, second.candidate, warnings)
    result = _merge_result(first.result, second.result, warnings)
    issue_info = _merge_issue_info(first.issue_info, second.issue_info, warnings)
    subjects = _merge_subjects(first.subjects, second.subjects, warnings)

    _check_required_fields(candidate, warnings)
    _check_marks_consistency(subjects, result, warnings)

    return MarksheetExtraction(
        candidate=candidate,
        subjects=subjects,
        result=result,
        issue_info=issue_info,
        document_confidence=_aggregate_confidence(candidate, subjects, result),
        warnings=warnings,
    )


def _merge_candidate(a: CandidateDetails, b: CandidateDetails, warnings: list[str]) -> CandidateDetails:
    return CandidateDetails(
        name=_merge_field(a.name, b.name, "candidate.name", warnings),
        father_name=_merge_field(a.father_name, b.father_name, "candidate.father_name", warnings),
        mother_name=_merge_field(a.mother_name, b.mother_name, "candidate.mother_name", warnings),
        roll_no=_merge_field(a.roll_no, b.roll_no, "candidate.roll_no", warnings),
        registration_no=_merge_field(a.registration_no, b.registration_no, "candidate.registration_no", warnings),
        date_of_birth=_merge_field(a.date_of_birth, b.date_of_birth, "candidate.date_of_birth", warnings),
        exam_year=_merge_field(a.exam_year, b.exam_year, "candidate.exam_year", warnings),
        board_or_university=_merge_field(a.board_or_university, b.board_or_university, "candidate.board_or_university", warnings),
        institution=_merge_field(a.institution, b.institution, "candidate.institution", warnings),
    )


def _merge_result(a: OverallResult, b: OverallResult, warnings: list[str]) -> OverallResult:
    return OverallResult(
        result=_merge_field(a.result, b.result, "result.result", warnings),
        division=_merge_field(a.division, b.division, "result.division", warnings),
        overall_grade=_merge_field(a.overall_grade, b.overall_grade, "result.overall_grade", warnings),
        percentage=_merge_numeric(a.percentage, b.percentage, "result.percentage", warnings),
        cgpa=_merge_numeric(a.cgpa, b.cgpa, "result.cgpa", warnings),
        sgpa=_merge_numeric(a.sgpa, b.sgpa, "result.sgpa", warnings),
        total_obtained_marks=_merge_numeric(a.total_obtained_marks, b.total_obtained_marks, "result.total_obtained_marks", warnings),
        total_max_marks=_merge_numeric(a.total_max_marks, b.total_max_marks, "result.total_max_marks", warnings),
    )


def _merge_issue_info(a: Optional[IssueInfo], b: Optional[IssueInfo], warnings: list[str]) -> Optional[IssueInfo]:
    if a is None and b is None:
        return None
    a, b = a or IssueInfo(), b or IssueInfo()
    return IssueInfo(
        issue_date=_merge_field(a.issue_date, b.issue_date, "issue_info.issue_date", warnings),
        issue_place=_merge_field(a.issue_place, b.issue_place, "issue_info.issue_place", warnings),
    )


def _merge_subjects(first: list[SubjectMark], second: list[SubjectMark], warnings: list[str]) -> list[SubjectMark]:
    if len(first) == len(second):
        pairs = list(zip(first, second))
    else:
        warnings.append(f"subjects: passes returned different counts ({len(first)} vs {len(second)}), using first model's subject list as anchor")
        pairs = _match_subjects_by_name(first, second)

    merged = []
    for index, (a, b) in enumerate(pairs):
        if b is None:
            merged.append(_solo_subject(a))
            continue
        path = f"subjects[{index}]"
        merged.append(SubjectMark(
            subject_name=_merge_field(a.subject_name, b.subject_name, f"{path}.subject_name", warnings),
            group=_merge_field(a.group, b.group, f"{path}.group", warnings),
            max_marks=_merge_numeric(a.max_marks, b.max_marks, f"{path}.max_marks", warnings),
            obtained_marks=_merge_numeric(a.obtained_marks, b.obtained_marks, f"{path}.obtained_marks", warnings),
            theory_marks=_merge_numeric(a.theory_marks, b.theory_marks, f"{path}.theory_marks", warnings),
            practical_marks=_merge_numeric(a.practical_marks, b.practical_marks, f"{path}.practical_marks", warnings),
            max_credits=_merge_numeric(a.max_credits, b.max_credits, f"{path}.max_credits", warnings),
            obtained_credits=_merge_numeric(a.obtained_credits, b.obtained_credits, f"{path}.obtained_credits", warnings),
            grade=_merge_field(a.grade, b.grade, f"{path}.grade", warnings),
        ))
    return merged


def _match_subjects_by_name(first: list[SubjectMark], second: list[SubjectMark]):
    remaining = list(second)
    pairs = []
    for subject in first:
        match = next(
            (s for s in remaining if _normalize(s.subject_name.value) == _normalize(subject.subject_name.value)),
            None,
        )
        if match:
            remaining.remove(match)
        pairs.append((subject, match))
    return pairs

def _merge_field(a, b, path, warnings):
    if a is None and b is None:
        return None
    if a is None or b is None:
        return _solo_field(a or b)
    if _normalize(a.value) == _normalize(b.value):
        return FieldValue(
            value=a.value,
            confidence=min(1.0, max(a.confidence, b.confidence) + AGREEMENT_BOOST),
            bbox=a.bbox if a.bbox is not None else b.bbox,
        )
    warnings.append(f"{path}: passes disagreed ('{a.value}' vs '{b.value}')")
    winner = a if a.confidence > b.confidence else b
    return _solo_field(winner)


def _merge_numeric(a, b, path, warnings):
    if a is None and b is None:
        return None
    if a is None or b is None:
        return _solo_numeric(a or b)
    if a.value == b.value:
        return NumericFieldValue(
            value=a.value,
            confidence=min(1.0, max(a.confidence, b.confidence) + AGREEMENT_BOOST),
            bbox=a.bbox if a.bbox is not None else b.bbox,
        )
    warnings.append(f"{path}: passes disagreed ({a.value} vs {b.value})")
    winner = a if a.confidence > b.confidence else b
    return _solo_numeric(winner)

def _solo_field(field):
    return None if field is None else FieldValue(
        value=field.value,
        confidence=field.confidence * DISAGREEMENT_PENALTY,
        bbox=field.bbox,
    )

def _solo_numeric(field):
    return None if field is None else NumericFieldValue(
        value=field.value,
        confidence=field.confidence * DISAGREEMENT_PENALTY,
        bbox=field.bbox,
    )

def _solo_subject(subject: SubjectMark) -> SubjectMark:
    return SubjectMark(
        subject_name=_solo_field(subject.subject_name),
        group=_solo_field(subject.group),
        max_marks=_solo_numeric(subject.max_marks),
        obtained_marks=_solo_numeric(subject.obtained_marks),
        theory_marks=_solo_numeric(subject.theory_marks),
        practical_marks=_solo_numeric(subject.practical_marks),
        max_credits=_solo_numeric(subject.max_credits),
        obtained_credits=_solo_numeric(subject.obtained_credits),
        grade=_solo_field(subject.grade),
    )


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _check_required_fields(candidate: CandidateDetails, warnings: list[str]) -> None:
    for field_name in REQUIRED_CANDIDATE_FIELDS:
        field = getattr(candidate, field_name)
        if field.value is None:
            warnings.append(f"required field candidate.{field_name} is missing")
            field.confidence = 0.0


def _check_marks_consistency(subjects: list[SubjectMark], result: OverallResult, warnings: list[str]) -> None:
    computed_total = sum(s.obtained_marks.value for s in subjects if s.obtained_marks and s.obtained_marks.value is not None)
    printed_total = result.total_obtained_marks.value if result.total_obtained_marks else None
    if computed_total == 0 or printed_total is None:
        return
    if abs(computed_total - printed_total) > 1:
        warnings.append(f"sum of subject marks ({computed_total}) does not match the printed total ({printed_total}) - possible nested/grouped subject structure")


def _aggregate_confidence(candidate: CandidateDetails, subjects: list[SubjectMark], result: OverallResult) -> float:
    scores = _collect(candidate) + _collect(result)
    for subject in subjects:
        scores += _collect(subject)
    return round(sum(scores) / len(scores), 3) if scores else 0.0


def _collect(model) -> list[float]:
    return [v["confidence"] for v in model.model_dump().values() if isinstance(v, dict) and "confidence" in v]