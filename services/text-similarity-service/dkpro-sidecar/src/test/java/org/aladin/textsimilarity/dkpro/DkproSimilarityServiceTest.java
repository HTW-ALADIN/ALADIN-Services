package org.aladin.textsimilarity.dkpro;

import org.aladin.textsimilarity.dkpro.model.SimilarityRequest;
import org.aladin.textsimilarity.dkpro.model.SimilarityResponse;
import org.aladin.textsimilarity.dkpro.service.DkproSimilarityService;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class DkproSimilarityServiceTest {

    private final DkproSimilarityService service = new DkproSimilarityService();

    @Test
    void topicModelLsaReturnsPlausibleValue() {
        SimilarityResponse response = service.computeSimilarity(
                "topic_model", "lsa", "The cat sat on the mat.", "A dog sat on the rug.");
        assertTrue(response.getSimilarity() >= 0.0 && response.getSimilarity() <= 1.0);
        assertTrue(response.getComputeTimeMs() >= 0.0);
    }

    @Test
    void structuralStylisticNgramContainment() {
        SimilarityResponse response = service.computeSimilarity(
                "structural_stylistic", "ngram_containment", "The cat sat on the mat.", "The cat sat on the mat.");
        assertTrue(response.getSimilarity() >= 0.0 && response.getSimilarity() <= 1.0);
    }

    @Test
    void unknownMeasureThrows() {
        assertThrows(IllegalArgumentException.class, () ->
                service.computeSimilarity("unknown", "lsa", "a", "b"));
    }

    // ── Optional backend extensions (Spec C §6.2) ─────────────────────────

    @Test
    void tokenSetReturnsPlausibleValue() {
        SimilarityResponse response = service.computeSimilarity(
                "token_set", "jaccard", "the cat sat on the mat", "the dog sat on the rug");
        assertTrue(response.getSimilarity() >= 0.0 && response.getSimilarity() <= 1.0);
    }

    @Test
    void lcsReturnsPlausibleValue() {
        SimilarityResponse response = service.computeSimilarity(
                "lcs", "common_substring", "kitten", "sitting");
        assertTrue(response.getSimilarity() >= 0.0 && response.getSimilarity() <= 1.0);
    }

    @Test
    void phoneticReturnsPlausibleValue() {
        SimilarityResponse response = service.computeSimilarity(
                "phonetic", "editex", "smith", "smyth");
        assertTrue(response.getSimilarity() >= 0.0 && response.getSimilarity() <= 1.0);
    }

    @Test
    void tfidfCosineReturnsPlausibleValue() {
        SimilarityResponse response = service.computeSimilarity(
                "tfidf_cosine", "cosine", "the cat sat on the mat", "the dog sat on the rug");
        assertTrue(response.getSimilarity() >= 0.0 && response.getSimilarity() <= 1.0);
    }

    @Test
    void wordnetSimilarityReturnsPlausibleValue() {
        SimilarityResponse response = service.computeSimilarity(
                "wordnet_similarity", "path", "dog", "cat");
        assertTrue(response.getSimilarity() >= 0.0 && response.getSimilarity() <= 1.0);
    }
}