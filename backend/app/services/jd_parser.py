from __future__ import annotations

import logging
import re
from typing import Final, TypedDict


logger = logging.getLogger(__name__)


class ParsedJD(TypedDict):
    cleaned_content: str
    required_skills: list[str]
    keywords: list[str]


_SKILL_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = tuple(
    (re.compile(pattern, flags=re.IGNORECASE), canonical)
    for pattern, canonical in (
        # Languages
        (r"\bpython\b", "python"),
        (r"\bjavascript\b", "javascript"),
        (r"\btypescript\b", "typescript"),
        (r"\bjava\b", "java"),
        (r"\bgolang\b|\bgo\b", "go"),
        (r"\brust\b", "rust"),
        (r"\bc\+\+", "c++"),
        (r"\bc#", "c#"),
        (r"\bscala\b", "scala"),
        (r"\bkotlin\b", "kotlin"),
        (r"\bswift\b", "swift"),
        # Frontend
        (r"\breact(?:\.js)?\b", "react"),
        (r"\bnext(?:\.js|js)\b", "next.js"),
        (r"\bvue(?:\.js)?\b", "vue"),
        (r"\bangular\b", "angular"),
        (r"\bsvelte\b", "svelte"),
        (r"\btailwind(?:css)?\b", "tailwind"),
        # Backend
        (r"\bfastapi\b", "fastapi"),
        (r"\bdjango\b", "django"),
        (r"\bflask\b", "flask"),
        (r"\bexpress(?:\.js)?\b", "express"),
        (r"\bnode(?:\.js|js)\b", "node.js"),
        (r"\bspring(?:\s+boot)?\b", "spring"),
        (r"\bgraphql\b", "graphql"),
        (r"\bgrpc\b", "grpc"),
        # Databases
        (r"\bpostgres(?:ql)?\b", "postgresql"),
        (r"\bmysql\b", "mysql"),
        (r"\bmongo(?:db)?\b", "mongodb"),
        (r"\bredis\b", "redis"),
        (r"\belasticsearch\b", "elasticsearch"),
        (r"\bdynamodb\b", "dynamodb"),
        (r"\bsqlite\b", "sqlite"),
        # Cloud / DevOps
        (r"\baws\b|\bamazon web services\b", "aws"),
        (r"\bgcp\b|\bgoogle cloud\b", "gcp"),
        (r"\bazure\b", "azure"),
        (r"\bdocker\b", "docker"),
        (r"\bkubernetes\b|\bk8s\b", "kubernetes"),
        (r"\bterraform\b", "terraform"),
        (r"\bci\s*/\s*cd\b|\bcontinuous integration\b|\bcontinuous delivery\b", "ci/cd"),
        # AI / ML
        (r"\bpytorch\b", "pytorch"),
        (r"\btensorflow\b", "tensorflow"),
        (r"\bscikit-learn\b|\bsklearn\b", "scikit-learn"),
        (r"\bpandas\b", "pandas"),
        (r"\bnumpy\b", "numpy"),
        (r"\blangchain\b", "langchain"),
        (r"\bllm\b", "llm"),
        (r"\brag\b", "rag"),
        # Data
        (r"\bsql\b", "sql"),
        (r"\bspark\b", "spark"),
        (r"\bkafka\b", "kafka"),
        (r"\bairflow\b", "airflow"),
        (r"\bdbt\b", "dbt"),
        (r"\bsnowflake\b", "snowflake"),
        (r"\bbigquery\b", "bigquery"),
        # Practices
        (r"\bgit\b", "git"),
        (r"\bagile\b", "agile"),
        (r"\bscrum\b", "scrum"),
        (r"\bsystem design\b", "system design"),
        (r"\bapi design\b", "api design"),
        (r"\btdd\b", "tdd"),
        (r"\bdevops\b", "devops"),
        (r"\bmicroservices\b", "microservices"),
    )
)

_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "you",
        "our",
        "are",
        "will",
        "have",
        "this",
        "that",
        "from",
        "your",
        "not",
        "but",
        "was",
        "been",
        "has",
        "more",
        "all",
        "can",
        "who",
        "may",
        "its",
        "also",
        "any",
        "new",
        "use",
        "using",
        "used",
        "work",
        "team",
        "able",
        "both",
        "well",
        "must",
        "such",
        "other",
        "into",
        "their",
        "they",
        "what",
        "when",
        "how",
        "which",
        "would",
        "could",
        "should",
        "each",
        "very",
        "experience",
        "strong",
        "knowledge",
        "skills",
        "ability",
        "working",
        "understanding",
        "including",
        "related",
        "across",
        "develop",
        "building",
        "build",
        "built",
        "design",
        "designed",
        "manage",
        "implement",
        "implementing",
        "excellent",
        "preferred",
        "required",
        "responsible",
        "looking",
        "join",
        "help",
        "within",
        "role",
        "position",
        "candidate",
        "company",
        "opportunity",
    }
)


def clean_jd_text(text: str) -> str:
    """Normalise line endings, collapse excess whitespace, and trim edges."""

    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    normalised = re.sub(r"[ \t\f\v]+", " ", normalised)
    normalised = "\n".join(line.strip() for line in normalised.split("\n"))
    normalised = re.sub(r"\n{3,}", "\n\n", normalised)
    return normalised.strip()


def extract_required_skills(text: str) -> list[str]:
    """Match text against a hardcoded skill set and return canonical skill names."""

    found: list[str] = []
    for pattern, canonical in _SKILL_PATTERNS:
        if pattern.search(text):
            found.append(canonical)
    return sorted(set(found))


def extract_keywords(text: str, max_keywords: int = 40) -> list[str]:
    """Extract ordered unique keywords from JD text with lightweight filtering."""

    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]*", text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for token in tokens:
        if len(token) < 3:
            continue
        if token in _STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def parse_jd(content: str) -> ParsedJD:
    """Run deterministic JD parsing and return cleaned content + extracted metadata."""

    if not content or not content.strip():
        raise ValueError("Job description content must not be empty.")

    cleaned = clean_jd_text(content)
    required_skills = extract_required_skills(cleaned)
    keywords = extract_keywords(cleaned)

    if not required_skills:
        logger.warning(
            "No technical skills detected in job description — "
            "may be a non-technical role (PM, design, etc.)."
        )

    return ParsedJD(
        cleaned_content=cleaned,
        required_skills=required_skills,
        keywords=keywords,
    )
