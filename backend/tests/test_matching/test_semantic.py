import pytest

from jobhunter.matching.semantic import build_corpus_stats, cosine_similarity, tokenize


def test_tokenize_drops_stopwords_and_short_tokens():
    tokens = tokenize("We are looking for a Senior Data Analyst with SQL skills")
    assert "senior" in tokens
    assert "data" in tokens
    assert "sql" in tokens
    assert "a" not in tokens
    assert "for" not in tokens


def test_build_corpus_stats_counts_documents():
    documents = ["python engineer position", "python data scientist position", "marketing manager position"]
    document_frequency, document_count = build_corpus_stats(documents)
    assert document_count == 3
    assert document_frequency["position"] == 3
    assert document_frequency["python"] == 2
    assert document_frequency["marketing"] == 1


def test_cosine_similarity_identical_vectors_is_one():
    vector = {"python": 2.0, "sql": 1.0}
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_cosine_similarity_disjoint_vectors_is_zero():
    assert cosine_similarity({"python": 1.0}, {"marketing": 1.0}) == 0.0


def test_cosine_similarity_empty_vector_is_zero():
    assert cosine_similarity({}, {"python": 1.0}) == 0.0
