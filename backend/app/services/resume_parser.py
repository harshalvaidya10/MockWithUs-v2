from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


SKILL_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Python", (r"\bpython\b",)),
    ("Java", (r"\bjava\b",)),
    ("JavaScript", (r"\bjavascript\b",)),
    ("TypeScript", (r"\btypescript\b",)),
    ("React", (r"\breact(?:\.js)?\b",)),
    ("Next.js", (r"\bnext(?:\.js|js)\b",)),
    ("Node.js", (r"\bnode(?:\.js|js)\b",)),
    ("FastAPI", (r"\bfastapi\b",)),
    ("SQL", (r"\bsql\b",)),
    ("PostgreSQL", (r"\bpostgres(?:ql)?\b",)),
    ("MongoDB", (r"\bmongo(?:db)?\b",)),
    ("Redis", (r"\bredis\b",)),
    ("Docker", (r"\bdocker\b",)),
    ("Kubernetes", (r"\bkubernetes\b|\bk8s\b",)),
    ("AWS", (r"\baws\b|\bamazon web services\b",)),
    ("GCP", (r"\bgcp\b|\bgoogle cloud\b",)),
    ("Git", (r"\bgit\b",)),
    ("Tailwind", (r"\btailwind(?:css)?\b",)),
    ("Spring Boot", (r"\bspring\s+boot\b",)),
    ("REST", (r"\brest(?:ful)?\b",)),
    ("GraphQL", (r"\bgraphql\b",)),
    ("CI/CD", (r"\bci\s*/\s*cd\b|\bcontinuous integration\b|\bcontinuous delivery\b",)),
)

NON_RESUME_UPLOAD_MESSAGE = (
    "Uploaded file does not appear to be a resume. "
    "Please upload a resume in PDF or DOCX format."
)

_RESUME_SECTION_PATTERNS: tuple[str, ...] = (
    r"(?mi)^\s*(professional\s+summary|summary|objective)\s*:?\s*$",
    r"(?mi)^\s*(work\s+experience|experience|employment\s+history)\s*:?\s*$",
    r"(?mi)^\s*(education)\s*:?\s*$",
    r"(?mi)^\s*(skills|technical\s+skills)\s*:?\s*$",
    r"(?mi)^\s*(projects)\s*:?\s*$",
    r"(?mi)^\s*(certifications)\s*:?\s*$",
)

_JOB_DESCRIPTION_PATTERNS: tuple[str, ...] = (
    r"\bresponsibilities\b",
    r"\brequirements\b",
    r"\bqualifications\b",
    r"\bpreferred qualifications\b",
    r"\bminimum qualifications\b",
    r"\babout the role\b",
    r"\babout the company\b",
    r"\bwhat you will do\b",
    r"\byou will be responsible\b",
    r"\bwe are looking for\b",
)

_DATE_RANGE_PATTERN = re.compile(
    r"\b(?:19|20)\d{2}\s*(?:-|–|to)\s*(?:present|current|(?:19|20)\d{2})\b",
    flags=re.IGNORECASE,
)

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", flags=re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\-\s().]{7,}\d)")
_LINKEDIN_PATTERN = re.compile(r"\blinkedin\.com/(?:in|pub)/", flags=re.IGNORECASE)
_GITHUB_PATTERN = re.compile(r"\bgithub\.com/", flags=re.IGNORECASE)
_BULLET_PATTERN = re.compile(r"(?m)^\s*(?:[-*•]\s+|\d+\.\s+)")
_NON_RESUME_FILENAME_PATTERN = re.compile(
    r"(?:^|[_\-\s.])("
    r"implementation[_\-\s]?plan|project[_\-\s]?plan|roadmap|proposal|"
    r"requirements?|spec(?:ification)?s?|sow|design[_\-\s]?doc"
    r")(?:[_\-\s.]|$)",
    flags=re.IGNORECASE,
)
_RESUME_FILENAME_HINT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(resume|cv|curriculum[-_\s]?vitae)(?![A-Za-z0-9])",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ResumeDocumentCheck:
    """Deterministic score output for resume-likeness validation."""

    is_likely_resume: bool
    confidence: float
    resume_score: int
    non_resume_score: int
    positive_signals: dict[str, int]
    negative_signals: dict[str, int]
    rejection_reason: str | None


def extract_text(file_path: str) -> str:
    """Extract raw text from a supported resume file."""

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return extract_text_from_pdf(file_path)
    if extension == ".docx":
        return extract_text_from_docx(file_path)

    raise ValueError("Unsupported file type. Only PDF and DOCX are allowed.")


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF using PyMuPDF."""

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF parsing dependency is not installed.") from exc

    try:
        with fitz.open(file_path) as document:
            pages = [page.get_text("text") for page in document]
    except Exception as exc:  # pragma: no cover - third-party exceptions vary.
        raise ValueError("Could not extract text from the uploaded file.") from exc

    return "\n".join(pages)


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX using python-docx."""

    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("DOCX parsing dependency is not installed.") from exc

    try:
        document = Document(file_path)
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
    except Exception as exc:  # pragma: no cover - third-party exceptions vary.
        raise ValueError("Could not extract text from the uploaded file.") from exc

    return "\n".join(paragraphs)


def clean_text(text: str) -> str:
    """Normalize whitespace and trim noisy line breaks."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def extract_skills(text: str) -> list[str]:
    """Extract known technical skills with stable ordering."""

    found_skills: list[str] = []

    for skill, patterns in SKILL_PATTERNS:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            found_skills.append(skill)

    return found_skills


def _count_regex_hits(patterns: tuple[str, ...], text: str) -> int:
    """Count distinct pattern matches (1 point per pattern with at least one hit)."""
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE))


def _clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a float to the inclusive [lower, upper] range."""
    return max(lower, min(upper, value))


def score_resume_likeness(text: str) -> ResumeDocumentCheck:
    """Score whether text resembles a resume using deterministic heuristics.

    The score combines:
    - Positive structure/content signals commonly found in resumes
    - Negative language cues commonly found in job descriptions
    """
    stripped_text = text.strip()
    if not stripped_text:
        return ResumeDocumentCheck(
            is_likely_resume=False,
            confidence=0.0,
            resume_score=0,
            non_resume_score=0,
            positive_signals={},
            negative_signals={},
            rejection_reason=NON_RESUME_UPLOAD_MESSAGE,
        )

    section_hits = _count_regex_hits(_RESUME_SECTION_PATTERNS, stripped_text)
    jd_phrase_hits = _count_regex_hits(_JOB_DESCRIPTION_PATTERNS, stripped_text)

    email_hits = len(_EMAIL_PATTERN.findall(stripped_text))
    phone_hits = len(_PHONE_PATTERN.findall(stripped_text))
    linkedin_hits = len(_LINKEDIN_PATTERN.findall(stripped_text))
    github_hits = len(_GITHUB_PATTERN.findall(stripped_text))
    date_range_hits = len(_DATE_RANGE_PATTERN.findall(stripped_text))
    bullet_hits = len(_BULLET_PATTERN.findall(stripped_text))
    technology_hits = len(extract_skills(stripped_text))

    contact_signal_count = int(email_hits > 0) + int(phone_hits > 0) + int(linkedin_hits > 0) + int(github_hits > 0)

    section_points = min(section_hits, 4) * 2
    contact_points = contact_signal_count * 2
    date_points = 3 if date_range_hits >= 2 else 2 if date_range_hits == 1 else 0
    bullet_points = 2 if bullet_hits >= 3 else 1 if bullet_hits >= 1 else 0
    technology_points = 3 if technology_hits >= 6 else 2 if technology_hits >= 3 else 1 if technology_hits >= 1 else 0

    resume_score = section_points + contact_points + date_points + bullet_points + technology_points

    jd_points = jd_phrase_hits * 2
    dense_narrative_penalty = 1 if bullet_hits == 0 and len(stripped_text.split()) > 250 else 0
    non_resume_score = jd_points + dense_narrative_penalty

    net_score = resume_score - non_resume_score
    confidence = _clamp((net_score + 12.0) / 24.0, 0.0, 1.0)
    is_likely_resume = resume_score >= 8 and net_score >= 2

    positive_signals = {
        "section_hits": section_hits,
        "contact_signals": contact_signal_count,
        "date_ranges": date_range_hits,
        "bullet_points": bullet_hits,
        "technology_keywords": technology_hits,
    }
    negative_signals = {
        "job_description_phrases": jd_phrase_hits,
        "dense_narrative_penalty": dense_narrative_penalty,
    }

    return ResumeDocumentCheck(
        is_likely_resume=is_likely_resume,
        confidence=confidence,
        resume_score=resume_score,
        non_resume_score=non_resume_score,
        positive_signals=positive_signals,
        negative_signals=negative_signals,
        rejection_reason=None if is_likely_resume else NON_RESUME_UPLOAD_MESSAGE,
    )


def assess_resume_text(text: str) -> tuple[bool, str]:
    """Backward-compatible bool/string wrapper around score_resume_likeness."""
    check = score_resume_likeness(text)
    return check.is_likely_resume, check.rejection_reason or ""


def assess_resume_document(text: str, filename: str | None = None) -> tuple[bool, str]:
    """Validate resume-ness using text signals plus filename heuristics."""
    check = score_resume_likeness(text)
    is_resume_like = check.is_likely_resume
    rejection_reason = check.rejection_reason or ""

    filename_value = (filename or "").strip()
    if filename_value:
        suspicious_filename = bool(_NON_RESUME_FILENAME_PATTERN.search(filename_value))
        explicit_resume_filename = bool(_RESUME_FILENAME_HINT_PATTERN.search(filename_value))
        if suspicious_filename and not explicit_resume_filename:
            return False, NON_RESUME_UPLOAD_MESSAGE

    return is_resume_like, rejection_reason


def parse_resume_file(file_path: str) -> dict[str, object]:
    """Parse resume text and derive lightweight metadata."""

    raw_text = extract_text(file_path)
    parsed_text = clean_text(raw_text)

    if not parsed_text:
        raise ValueError("Could not extract text from the uploaded file.")

    skills = extract_skills(parsed_text)
    return {"parsed_text": parsed_text, "skills": skills}
