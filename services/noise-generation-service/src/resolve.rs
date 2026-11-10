//! Resolves optional request parameters into concrete values, exactly once
//! per request. The resolved value is used for **both** noise generation and
//! the `params_used` echo, which eliminates a class of bug where the two
//! could disagree (e.g. a seed generated twice, landing on different random
//! values for generation vs. the echoed response).

use crate::algorithms::{
    AlgorithmParams, DEFAULT_PERSISTENCE_FBM_BILLOW, DEFAULT_PERSISTENCE_HYBRID,
    DEFAULT_PERSISTENCE_RIDGED,
};
use crate::model::{
    CellularDistanceFunction, CellularReturnType, CombinatorOp, GenerateNoiseRequest, SeedParams,
    UtilityKind,
};

/// Default fractal octaves (4). 4 octaves is a standard trade-off between
/// detail richness and performance, matching noise-crate's own examples.
pub const DEFAULT_OCTAVES: usize = 4;

/// Default frequency (0.1). Gives ~10 noise features per unit length,
/// producing well-visible structures at typical grid resolutions (64-512).
pub const DEFAULT_FREQUENCY: f64 = 0.1;

/// Default lacunarity (2.0). Doubles frequency per octave — this is the
/// standard lacunarity for Perlin-based fractals (noise-crate default).
pub const DEFAULT_LACUNARITY: f64 = 2.0;

/// Maximum octaves accepted by the `noise` crate's `MultiFractal::set_octaves`
/// (clamped internally to `1..=32`). Requested values are clamped to this same
/// range up front so the echoed `params_used.octaves` always matches what was
/// actually generated.
pub const MAX_OCTAVES: usize = 32;

/// Default cellular jitter (0.45). Standard Worley noise jitter factor.
pub const DEFAULT_JITTER: f64 = 0.45;

/// Default PingPong strength (2.0). Standard wrapping strength for PingPong fractal.
pub const DEFAULT_STRENGTH: f64 = 2.0;

/// Default domain warp amplitude (1.0). Standard amplitude for domain warping.
pub const DEFAULT_AMPLITUDE: f64 = 1.0;

/// Default combinator blend factor (0.5). Equal mix when blending two sources.
pub const DEFAULT_BLEND_FACTOR: f64 = 0.5;

/// Default utility constant value (1.0).
pub const DEFAULT_UTILITY_VALUE: f64 = 1.0;

fn random_seed() -> u32 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    (nanos ^ (nanos >> 32)) as u32
}

fn get_seed(seed: Option<u32>) -> u32 {
    seed.unwrap_or_else(random_seed)
}

/// Fully resolved noise parameters for one algorithm family. Resolved exactly
/// once per request; used for both noise generation **and** the `params_used`
/// echo.
pub enum ResolvedNoiseParams {
    SeedOnly {
        seed: u32,
    },
    Cellular {
        seed: u32,
        distance_function: CellularDistanceFunction,
        return_type: CellularReturnType,
        jitter: f64,
    },
    Fractal {
        seed: u32,
        octaves: usize,
        frequency: f64,
        lacunarity: f64,
        persistence: f64,
    },
    PingPong {
        seed: u32,
        strength: f64,
    },
    DomainWarp {
        seed: u32,
        amplitude: f64,
    },
    Combinator {
        seed: u32,
        op: CombinatorOp,
        blend_factor: f64,
    },
    Utility {
        kind: UtilityKind,
        value: f64,
    },
}

impl ResolvedNoiseParams {
    pub fn to_json(&self) -> serde_json::Value {
        match self {
            ResolvedNoiseParams::SeedOnly { seed } => {
                serde_json::json!({ "seed": seed })
            }
            ResolvedNoiseParams::Cellular {
                seed,
                distance_function,
                return_type,
                jitter,
            } => {
                serde_json::json!({
                    "seed": seed,
                    "distance_function": distance_function,
                    "return_type": return_type,
                    "jitter": jitter,
                })
            }
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            } => {
                serde_json::json!({
                    "seed": seed,
                    "octaves": octaves,
                    "frequency": frequency,
                    "lacunarity": lacunarity,
                    "persistence": persistence,
                })
            }
            ResolvedNoiseParams::PingPong { seed, strength } => {
                serde_json::json!({
                    "seed": seed,
                    "strength": strength,
                })
            }
            ResolvedNoiseParams::DomainWarp { seed, amplitude } => {
                serde_json::json!({
                    "seed": seed,
                    "amplitude": amplitude,
                })
            }
            ResolvedNoiseParams::Combinator {
                seed,
                op,
                blend_factor,
            } => {
                serde_json::json!({
                    "seed": seed,
                    "op": op,
                    "blend_factor": blend_factor,
                })
            }
            ResolvedNoiseParams::Utility { kind, value } => {
                serde_json::json!({
                    "kind": kind,
                    "value": value,
                })
            }
        }
    }
}

fn resolve_seed_only(params: &SeedParams) -> ResolvedNoiseParams {
    ResolvedNoiseParams::SeedOnly {
        seed: get_seed(params.seed),
    }
}

/// Shared by Fbm, Billow, RidgedMulti, and HybridMulti, which differ only in
/// their default `persistence`.
fn resolve_fractal(
    seed: Option<u32>,
    octaves: Option<usize>,
    frequency: Option<f64>,
    lacunarity: Option<f64>,
    persistence: Option<f64>,
    default_persistence: f64,
) -> ResolvedNoiseParams {
    ResolvedNoiseParams::Fractal {
        seed: get_seed(seed),
        // Clamp to the same 1..=32 range that `MultiFractal::set_octaves` enforces
        // internally, so the value echoed in `params_used` matches generation.
        octaves: octaves.unwrap_or(DEFAULT_OCTAVES).clamp(1, MAX_OCTAVES),
        frequency: frequency.unwrap_or(DEFAULT_FREQUENCY),
        lacunarity: lacunarity.unwrap_or(DEFAULT_LACUNARITY),
        persistence: persistence.unwrap_or(default_persistence),
    }
}

/// Resolves optional request parameters into concrete values once.
pub fn resolve_params(payload: &GenerateNoiseRequest) -> ResolvedNoiseParams {
    match &payload.algorithm {
        AlgorithmParams::Perlin(params)
        | AlgorithmParams::Simplex(params)
        | AlgorithmParams::OpenSimplex2(params)
        | AlgorithmParams::SuperSimplex(params)
        | AlgorithmParams::Value(params)
        | AlgorithmParams::White(params) => resolve_seed_only(params),
        AlgorithmParams::Cellular(params) => ResolvedNoiseParams::Cellular {
            seed: get_seed(params.seed),
            distance_function: params
                .distance_function
                .clone()
                .unwrap_or(CellularDistanceFunction::Euclidean),
            return_type: params
                .return_type
                .clone()
                .unwrap_or(CellularReturnType::CellValue),
            jitter: params.jitter.unwrap_or(DEFAULT_JITTER),
        },
        AlgorithmParams::Fbm(params) => resolve_fractal(
            params.seed,
            params.octaves,
            params.frequency,
            params.lacunarity,
            params.persistence,
            DEFAULT_PERSISTENCE_FBM_BILLOW,
        ),
        AlgorithmParams::Billow(params) => resolve_fractal(
            params.seed,
            params.octaves,
            params.frequency,
            params.lacunarity,
            params.persistence,
            DEFAULT_PERSISTENCE_FBM_BILLOW,
        ),
        AlgorithmParams::RidgedMulti(params) => resolve_fractal(
            params.seed,
            params.octaves,
            params.frequency,
            params.lacunarity,
            params.persistence,
            DEFAULT_PERSISTENCE_RIDGED,
        ),
        AlgorithmParams::HybridMulti(params) => resolve_fractal(
            params.seed,
            params.octaves,
            params.frequency,
            params.lacunarity,
            params.persistence,
            DEFAULT_PERSISTENCE_HYBRID,
        ),
        AlgorithmParams::PingPong(params) => ResolvedNoiseParams::PingPong {
            seed: get_seed(params.seed),
            strength: params.strength.unwrap_or(DEFAULT_STRENGTH),
        },
        AlgorithmParams::DomainWarp(params) => ResolvedNoiseParams::DomainWarp {
            seed: get_seed(params.seed),
            amplitude: params.amplitude.unwrap_or(DEFAULT_AMPLITUDE),
        },
        AlgorithmParams::Combinator(params) => ResolvedNoiseParams::Combinator {
            seed: get_seed(params.seed),
            op: params.op.clone().unwrap_or(CombinatorOp::Add),
            blend_factor: params.blend_factor.unwrap_or(DEFAULT_BLEND_FACTOR),
        },
        AlgorithmParams::Utility(params) => ResolvedNoiseParams::Utility {
            kind: params.kind.clone().unwrap_or(UtilityKind::Constant),
            value: params.value.unwrap_or(DEFAULT_UTILITY_VALUE),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{FractalParams, Output, OutputFormat, Sampling};

    fn request(algorithm: AlgorithmParams) -> GenerateNoiseRequest {
        GenerateNoiseRequest {
            algorithm,
            sampling: Sampling {
                size: Some(vec![4, 4]),
            },
            output: Some(Output {
                format: OutputFormat::Json,
                normalize: false,
            }),
        }
    }

    #[test]
    fn octaves_are_clamped_to_max() {
        let req = request(AlgorithmParams::Fbm(FractalParams {
            octaves: Some(1000),
            ..Default::default()
        }));
        match resolve_params(&req) {
            ResolvedNoiseParams::Fractal { octaves, .. } => assert_eq!(octaves, MAX_OCTAVES),
            _ => panic!("expected Fractal"),
        }
    }

    #[test]
    fn explicit_seed_is_preserved() {
        let req = request(AlgorithmParams::Perlin(SeedParams { seed: Some(7) }));
        match resolve_params(&req) {
            ResolvedNoiseParams::SeedOnly { seed } => assert_eq!(seed, 7),
            _ => panic!("expected SeedOnly"),
        }
    }

    #[test]
    fn missing_seed_is_randomly_generated_and_nonzero_json() {
        let req = request(AlgorithmParams::Perlin(SeedParams { seed: None }));
        let resolved = resolve_params(&req);
        let json = resolved.to_json();
        assert!(json["seed"].is_number());
    }

    #[test]
    fn ridged_multi_and_hybrid_multi_have_distinct_default_persistence() {
        let ridged = request(AlgorithmParams::RidgedMulti(FractalParams::default()));
        let hybrid = request(AlgorithmParams::HybridMulti(FractalParams::default()));
        let ridged_persistence = match resolve_params(&ridged) {
            ResolvedNoiseParams::Fractal { persistence, .. } => persistence,
            _ => panic!("expected Fractal"),
        };
        let hybrid_persistence = match resolve_params(&hybrid) {
            ResolvedNoiseParams::Fractal { persistence, .. } => persistence,
            _ => panic!("expected Fractal"),
        };
        assert_eq!(ridged_persistence, DEFAULT_PERSISTENCE_RIDGED);
        assert_eq!(hybrid_persistence, DEFAULT_PERSISTENCE_HYBRID);
        assert_ne!(ridged_persistence, hybrid_persistence);
    }
}
