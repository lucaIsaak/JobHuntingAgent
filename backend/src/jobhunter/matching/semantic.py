"""Layer C: semantic similarity via hand-rolled TF-IDF + cosine (no sklearn/torch).

Document frequencies are computed once over the *whole* active jobs table (see
`jobs_repository.save_corpus_stats`/`get_corpus_stats`, rebuilt by `jobs/seed_loader.py`) rather
than per match run, so IDF — and therefore semantic scores — stay comparable across candidates and
runs, and don't degenerate when the prefiltered candidate set is small. A term absent from the
corpus gets the maximal/rarest IDF (treated as maximally specific).

Profile text is built from the structured profile (skills + recent titles + headline + industries
+ top achievements) — never the raw CV, per spec. Job text is title + must-have requirements +
description.
"""

from __future__ import annotations

import math
import re
from typing import Protocol

import numpy as np

from jobhunter.candidate.schema import CandidateProfile
from jobhunter.jobs.schema import Job

_TOKEN_RE = re.compile(r"[a-zà-ÿ]{2,}")
_STOPWORDS = {
    "the", "and", "of", "to", "in", "a", "for", "with", "on", "is", "at", "as", "an", "by",
    "or", "we", "you", "our", "your", "are", "be", "will", "have", "has", "this", "that",
    "from", "team", "role", "work", "years", "experience", "job", "using",
}


def tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS]


def build_corpus_stats(documents: list[str]) -> tuple[dict[str, int], int]:
    """Document frequency per term across the given documents, plus the document count."""
    document_frequency: dict[str, int] = {}
    for document in documents:
        for term in set(tokenize(document)):
            document_frequency[term] = document_frequency.get(term, 0) + 1
    return document_frequency, len(documents)


def _idf(term: str, document_frequency: dict[str, int], document_count: int) -> float:
    df = document_frequency.get(term, 0)
    return math.log((document_count + 1) / (df + 1)) + 1


def _tfidf_vector(text: str, document_frequency: dict[str, int], document_count: int) -> dict[str, float]:
    tokens = tokenize(text)
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    max_count = max(counts.values())
    return {
        term: (0.5 + 0.5 * (count / max_count)) * _idf(term, document_frequency, document_count)
        for term, count in counts.items()
    }


def cosine_similarity(vector_a: dict[str, float], vector_b: dict[str, float]) -> float:
    if not vector_a or not vector_b:
        return 0.0
    vocabulary = sorted(set(vector_a) | set(vector_b))
    a = np.array([vector_a.get(term, 0.0) for term in vocabulary])
    b = np.array([vector_b.get(term, 0.0) for term in vocabulary])
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(float(np.dot(a, b) / (norm_a * norm_b)), 1.0))


def profile_text(profile: CandidateProfile, recent_roles: int = 3, top_achievements: int = 5) -> str:
    parts: list[str] = []
    if profile.headline:
        parts.append(profile.headline)
    recent = sorted(profile.experience, key=lambda entry: entry.start_date or "", reverse=True)[:recent_roles]
    parts.extend(entry.normalized_title for entry in recent)
    parts.extend(skill.normalized_name for skill in profile.skills)
    parts.extend(profile.industries)
    achievements = [achievement.text for entry in profile.experience for achievement in entry.achievements]
    parts.extend(achievements[:top_achievements])
    return " ".join(parts)


def job_text(job: Job) -> str:
    return " ".join([job.title, " ".join(job.requirements_must), job.description])


class EmbeddingProvider(Protocol):
    """Swap point for a real embeddings API later without touching the engine."""

    def similarity(
        self, profile: CandidateProfile, job: Job, document_frequency: dict[str, int], document_count: int
    ) -> float: ...


class TfIdfEmbeddingProvider:
    def similarity(
        self, profile: CandidateProfile, job: Job, document_frequency: dict[str, int], document_count: int
    ) -> float:
        candidate_vector = _tfidf_vector(profile_text(profile), document_frequency, document_count)
        job_vector = _tfidf_vector(job_text(job), document_frequency, document_count)
        return cosine_similarity(candidate_vector, job_vector)
