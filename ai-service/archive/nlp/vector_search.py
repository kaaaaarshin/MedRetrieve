from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def find_best_matches(
    query: str,
    icd_entries: list[dict],
    top_k: int = 3,
):
    corpus = [query]

    for icd in icd_entries:
        corpus.append(icd["description"])

    vectorizer = TfidfVectorizer(
        stop_words="english"
    )

    matrix = vectorizer.fit_transform(corpus)

    query_vector = matrix[0]

    icd_vectors = matrix[1:]

    scores = cosine_similarity(
        query_vector,
        icd_vectors
    )[0]

    results = []

    for idx, score in enumerate(scores):
        results.append({
            "code": icd_entries[idx]["code"],
            "description": icd_entries[idx]["description"],
            "score": float(score),
        })

    results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return results[:top_k]