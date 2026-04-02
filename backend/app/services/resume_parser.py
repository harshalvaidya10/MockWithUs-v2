from __future__ import annotations

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


def parse_resume_file(file_path: str) -> dict[str, object]:
    """Parse resume text and derive lightweight metadata."""

    raw_text = extract_text(file_path)
    parsed_text = clean_text(raw_text)

    if not parsed_text:
        raise ValueError("Could not extract text from the uploaded file.")

    skills = extract_skills(parsed_text)
    return {"parsed_text": parsed_text, "skills": skills}
