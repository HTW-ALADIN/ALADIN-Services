//! Noise generation service library.
//!
//! Module layout:
//! - [`algorithms`]: the single source of truth for the set of supported
//!   algorithms — wire names, the tagged [`AlgorithmParams`] enum, and
//!   per-algorithm dimension support.
//! - [`model`]: request/response DTOs and per-algorithm parameter structs.
//! - [`dim`]: the `Dim` enum and shared grid-iteration helpers.
//! - [`resolve`]: turns optional request parameters into concrete resolved
//!   values, used for both generation and the `params_used` echo.
//! - [`generate`]: the noise generation kernels (one per algorithm family).
//! - [`shape`]: reshapes a flat generation buffer into nested response JSON.
//! - [`error`]: structured request-validation errors.
//! - [`service`]: the HTTP-free core `generate` function shared by the HTTP
//!   handler and the CLI.
//! - [`http`]: thin axum handlers.
//! - [`openapi`]: the `utoipa` `ApiDoc` schema registration.
//! - [`cli`]: `clap` CLI argument definitions, shared by the binary and by
//!   `tests/cli_tests.rs` via this public module.

// Range loops and casts are clearer for noise generation — allowed via the
// `[lints.clippy]` table in Cargo.toml, which applies uniformly to the lib
// and bin targets instead of a per-crate `#![allow(...)]`.

pub mod algorithms;
pub mod cli;
pub mod dim;
pub mod error;
pub mod generate;
pub mod http;
pub mod limits;
pub mod model;
pub mod openapi;
pub mod render;
pub mod resolve;
pub mod service;
pub mod shape;

// Re-export the most commonly used items at the crate root so callers
// (the binary, integration tests) don't need to know the internal module
// layout.
pub use algorithms::{AlgorithmParams, ALGORITHM_NAMES};
pub use error::NoiseError;
pub use http::{generate_noise, list_algorithms};
pub use model::{
    AlgorithmInfo, CellularDistanceFunction, CellularParams, CellularReturnType, CombinatorOp,
    CombinatorParams, DomainWarpParams, FractalParams, GenerateNoiseRequest, NoiseFieldResult,
    Output, OutputFormat, PingPongParams, Sampling, SeedParams, UtilityKind, UtilityParams,
};
pub use openapi::ApiDoc;

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    /// Verify that the JSON wire format matches the expected layout:
    ///   { "algorithm": "perlin", "params": {...}, "sampling": {...}, "output": {...} }
    /// The order of keys in the serialized JSON is determined by serde's flatten
    /// behavior — the only requirement is that the four keys exist with correct values.
    #[test]
    fn test_serialization_perlin() {
        let req = GenerateNoiseRequest {
            algorithm: AlgorithmParams::Perlin(SeedParams { seed: Some(42) }),
            sampling: Sampling {
                size: Some(vec![64, 64]),
            },
            output: Some(Output {
                format: OutputFormat::Json,
                normalize: false,
            }),
        };
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["algorithm"], "perlin");
        assert_eq!(json["params"]["seed"], 42);
        assert_eq!(json["sampling"]["size"], serde_json::json!([64, 64]));
        assert_eq!(json["output"]["format"], "json");
        assert_eq!(json["output"]["normalize"], false);
        let keys: BTreeSet<&str> = json
            .as_object()
            .unwrap()
            .keys()
            .map(|k| k.as_str())
            .collect();
        let expected: BTreeSet<&str> = ["algorithm", "params", "sampling", "output"].into();
        assert_eq!(keys, expected);
    }

    #[test]
    fn test_serialization_fbm() {
        let req = GenerateNoiseRequest {
            algorithm: AlgorithmParams::Fbm(FractalParams {
                seed: Some(42),
                octaves: Some(4),
                frequency: Some(0.1),
                lacunarity: Some(2.0),
                persistence: Some(0.5),
            }),
            sampling: Sampling {
                size: Some(vec![32, 32]),
            },
            output: None,
        };
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["algorithm"], "fbm");
        assert_eq!(json["params"]["seed"], 42);
        assert_eq!(json["params"]["octaves"], 4);
        assert_eq!(json["sampling"]["size"], serde_json::json!([32, 32]));
        assert!(json["output"].is_null());
    }

    #[test]
    fn test_serialization_cellular() {
        let req = GenerateNoiseRequest {
            algorithm: AlgorithmParams::Cellular(CellularParams {
                seed: Some(123),
                distance_function: Some(CellularDistanceFunction::EuclideanSq),
                return_type: Some(CellularReturnType::Distance2),
                jitter: Some(0.6),
            }),
            sampling: Sampling {
                size: Some(vec![16, 16]),
            },
            output: Some(Output {
                format: OutputFormat::Csv,
                normalize: true,
            }),
        };
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["algorithm"], "cellular");
        assert_eq!(json["params"]["seed"], 123);
        assert_eq!(json["params"]["distance_function"], "euclidean_sq");
        assert_eq!(json["params"]["return_type"], "distance2");
        assert_eq!(json["params"]["jitter"], 0.6);
        assert_eq!(json["output"]["format"], "csv");
        assert_eq!(json["output"]["normalize"], true);
    }

    #[test]
    fn test_deserialization_roundtrip() {
        let json_str = r#"{"algorithm":"perlin","params":{"seed":42},"sampling":{"size":[64,64]},"output":{"format":"json","normalize":false}}"#;
        let req: GenerateNoiseRequest = serde_json::from_str(json_str).unwrap();
        assert_eq!(req.algorithm.name(), "perlin");
        assert_eq!(req.sampling_size(), Some(vec![64, 64]));
        assert!(!req.should_normalize());
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["algorithm"], "perlin");
        assert_eq!(json["params"]["seed"], 42);
    }

    #[test]
    fn test_deserialization_fbm_roundtrip() {
        let json_str = r#"{"algorithm":"fbm","params":{"seed":42,"octaves":4,"frequency":0.1,"lacunarity":2.0,"persistence":0.5},"sampling":{"size":[32,32]},"output":null}"#;
        let req: GenerateNoiseRequest = serde_json::from_str(json_str).unwrap();
        assert_eq!(req.algorithm.name(), "fbm");
        assert_eq!(req.sampling_size(), Some(vec![32, 32]));
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["algorithm"], "fbm");
        assert_eq!(json["params"]["seed"], 42);
    }

    #[test]
    fn test_deserialization_cellular_roundtrip() {
        let json_str = r#"{"algorithm":"cellular","params":{"seed":123,"distance_function":"euclidean_sq","return_type":"distance2","jitter":0.6},"sampling":{"size":[16,16]},"output":{"format":"csv","normalize":true}}"#;
        let req: GenerateNoiseRequest = serde_json::from_str(json_str).unwrap();
        assert_eq!(req.algorithm.name(), "cellular");
        assert_eq!(req.sampling_size(), Some(vec![16, 16]));
        assert!(req.should_normalize());
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["algorithm"], "cellular");
        assert_eq!(json["params"]["distance_function"], "euclidean_sq");
    }
}
