package org.aladin.textsimilarity.dkpro.controller;

import org.aladin.textsimilarity.dkpro.model.SimilarityRequest;
import org.aladin.textsimilarity.dkpro.model.SimilarityResponse;
import org.aladin.textsimilarity.dkpro.service.DkproSimilarityService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/v1/dkpro")
public class DkproSimilarityController {

    private final DkproSimilarityService service;

    public DkproSimilarityController(DkproSimilarityService service) {
        this.service = service;
    }

    @PostMapping("/similarity")
    public ResponseEntity<?> computeSimilarity(@RequestBody SimilarityRequest request) {
        try {
            SimilarityResponse response = service.computeSimilarity(
                    request.getMeasure(),
                    request.getVariant(),
                    request.getTextA(),
                    request.getTextB());
            return ResponseEntity.ok(response);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(java.util.Map.of("error", e.getMessage()));
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                    .body(java.util.Map.of("error", "Internal error: " + e.getMessage()));
        }
    }

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        return ResponseEntity.ok(java.util.Map.of(
                "status", "ok",
                "service", "text-similarity-dkpro-service"));
    }
}