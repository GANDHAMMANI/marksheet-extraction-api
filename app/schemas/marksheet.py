from typing import Optional
from pydantic import BaseModel, Field

class FieldValue(BaseModel):
    value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Optional[list[float]] = None


class NumericFieldValue(BaseModel):
    value: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Optional[list[float]] = None


class CandidateDetails(BaseModel):
    name: FieldValue
    father_name: Optional[FieldValue] = None
    mother_name: Optional[FieldValue] = None
    roll_no: FieldValue
    registration_no: Optional[FieldValue] = None
    date_of_birth: Optional[FieldValue] = None
    exam_year: Optional[FieldValue] = None
    board_or_university: FieldValue
    institution: Optional[FieldValue] = None


class SubjectMark(BaseModel):
    subject_name: FieldValue
    group: Optional[FieldValue] = None
    max_marks: Optional[NumericFieldValue] = None
    obtained_marks: Optional[NumericFieldValue] = None
    theory_marks: Optional[NumericFieldValue] = None
    practical_marks: Optional[NumericFieldValue] = None
    max_credits: Optional[NumericFieldValue] = None
    obtained_credits: Optional[NumericFieldValue] = None
    grade: Optional[FieldValue] = None


class OverallResult(BaseModel):
    result: Optional[FieldValue] = None
    division: Optional[FieldValue] = None
    overall_grade: Optional[FieldValue] = None
    percentage: Optional[NumericFieldValue] = None
    cgpa: Optional[NumericFieldValue] = None
    sgpa: Optional[NumericFieldValue] = None
    total_obtained_marks: Optional[NumericFieldValue] = None
    total_max_marks: Optional[NumericFieldValue] = None


class IssueInfo(BaseModel):
    issue_date: Optional[FieldValue] = None
    issue_place: Optional[FieldValue] = None


class MarksheetExtraction(BaseModel):
    candidate: CandidateDetails
    subjects: list[SubjectMark]
    result: OverallResult
    issue_info: Optional[IssueInfo] = None
    document_confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = []
    


class BatchItemResult(BaseModel):
    filename: str
    success: bool
    data: Optional[MarksheetExtraction] = None
    error: Optional[str] = None