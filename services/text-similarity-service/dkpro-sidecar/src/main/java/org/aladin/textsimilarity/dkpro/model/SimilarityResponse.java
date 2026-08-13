package org.aladin.textsimilarity.dkpro.model;

import java.util.Map;

public class SimilarityResponse {
    private String measure;
    private String variant;
    private double similarity;
    private double distance;
    private double computeTimeMs;

    public SimilarityResponse() {}

    public SimilarityResponse(String measure, String variant, double similarity, double distance, double computeTimeMs) {
        this.measure = measure;
        this.variant = variant;
        this.similarity = similarity;
        this.distance = distance;
        this.computeTimeMs = computeTimeMs;
    }

    public String getMeasure() { return measure; }
    public void setMeasure(String measure) { this.measure = measure; }

    public String getVariant() { return variant; }
    public void setVariant(String variant) { this.variant = variant; }

    public double getSimilarity() { return similarity; }
    public void setSimilarity(double similarity) { this.similarity = similarity; }

    public double getDistance() { return distance; }
    public void setDistance(double distance) { this.distance = distance; }

    public double getComputeTimeMs() { return computeTimeMs; }
    public void setComputeTimeMs(double computeTimeMs) { this.computeTimeMs = computeTimeMs; }
}