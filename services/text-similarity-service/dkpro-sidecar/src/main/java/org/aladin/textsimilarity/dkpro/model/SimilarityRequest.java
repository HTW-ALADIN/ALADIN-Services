package org.aladin.textsimilarity.dkpro.model;

import java.util.Map;

public class SimilarityRequest {
    private String measure;
    private String variant;
    private String textA;
    private String textB;
    private Map<String, Object> params;

    public SimilarityRequest() {}

    public String getMeasure() { return measure; }
    public void setMeasure(String measure) { this.measure = measure; }

    public String getVariant() { return variant; }
    public void setVariant(String variant) { this.variant = variant; }

    public String getTextA() { return textA; }
    public void setTextA(String textA) { this.textA = textA; }

    public String getTextB() { return textB; }
    public void setTextB(String textB) { this.textB = textB; }

    public Map<String, Object> getParams() { return params; }
    public void setParams(Map<String, Object> params) { this.params = params; }
}