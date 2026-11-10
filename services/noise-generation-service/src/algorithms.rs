//! Single source of truth for the set of supported noise algorithms.
//!
//! The [`algorithms!`] macro below generates the wire-tagged
//! [`AlgorithmParams`] enum, the algorithm name lookup, and the
//! dimension-support table from one declarative list. `ALGORITHM_NAMES` and
//! `AlgorithmParams::name`/`AlgorithmParams::dim_support` are then the only
//! things any other code (HTTP handlers, the CLI, tests) needs to consult.

use crate::dim::Dim;
use crate::model::{
    CellularParams, CombinatorParams, DomainWarpParams, FractalParams, PingPongParams, SeedParams,
    UtilityParams,
};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

/// Which sampling dimensionalities an algorithm family supports.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DimSupport {
    /// 2D and 3D only (most FastNoiseLite-backed algorithms, domain warp,
    /// noise-crate's `SuperSimplex`).
    D2D3,
    /// 2D, 3D, and 4D (noise-crate types implementing `NoiseFn<f64, 4>`).
    D2D3D4,
    /// 1D, 2D, 3D, and 4D (the native white-noise hash, which has no
    /// dimensionality restriction from an external library).
    All,
}

impl DimSupport {
    pub fn supports(&self, dim: Dim) -> bool {
        match self {
            DimSupport::D2D3 => matches!(dim, Dim::D2 | Dim::D3),
            DimSupport::D2D3D4 => matches!(dim, Dim::D2 | Dim::D3 | Dim::D4),
            DimSupport::All => true,
        }
    }

    /// Human-readable reason shown in dimension-rejection error messages.
    /// Only ever called after `supports()` returns `false` (see
    /// `crate::service::generate`), so `DimSupport::All` — which supports
    /// every dimensionality and thus never rejects — can never reach here.
    pub fn reason(&self) -> &'static str {
        match self {
            DimSupport::D2D3 => "only 2D/3D sampling is supported",
            DimSupport::D2D3D4 => "1D sampling is not supported (requires at least 2D)",
            DimSupport::All => unreachable!("DimSupport::All supports every dimension"),
        }
    }
}

macro_rules! algorithms {
    ($(($variant:ident, $wire:literal, $params:ty, $dims:expr)),* $(,)?) => {
        #[derive(Serialize, Deserialize, Debug, ToSchema)]
        #[serde(tag = "algorithm", content = "params")]
        pub enum AlgorithmParams {
            $(
                #[serde(rename = $wire)]
                $variant(#[serde(default)] $params),
            )*
        }

        impl AlgorithmParams {
            /// The wire-format name of this algorithm, e.g. `"perlin"`.
            pub fn name(&self) -> &'static str {
                match self {
                    $(AlgorithmParams::$variant(..) => $wire,)*
                }
            }

            /// Which sampling dimensionalities this algorithm supports.
            pub fn dim_support(&self) -> DimSupport {
                match self {
                    $(AlgorithmParams::$variant(..) => $dims,)*
                }
            }
        }

        /// Every algorithm's wire-format name, in declaration order. This is
        /// the single source used by `GET /v1/algorithms` and by CLI
        /// argument validation — neither maintains its own copy of the list.
        pub const ALGORITHM_NAMES: &[&str] = &[$($wire),*];
    };
}

algorithms! {
    (Perlin,       "perlin",       SeedParams,      DimSupport::D2D3),
    (Simplex,      "simplex",      SeedParams,      DimSupport::D2D3D4),
    (OpenSimplex2, "opensimplex2", SeedParams,      DimSupport::D2D3),
    (SuperSimplex, "supersimplex", SeedParams,      DimSupport::D2D3),
    (Value,        "value",        SeedParams,      DimSupport::D2D3),
    (Cellular,     "cellular",     CellularParams,  DimSupport::D2D3),
    (Fbm,          "fbm",          FractalParams,   DimSupport::D2D3D4),
    (Billow,       "billow",       FractalParams,   DimSupport::D2D3D4),
    (RidgedMulti,  "ridged_multi", FractalParams,   DimSupport::D2D3D4),
    (HybridMulti,  "hybrid_multi", FractalParams,   DimSupport::D2D3D4),
    (PingPong,     "pingpong",     PingPongParams,  DimSupport::D2D3),
    (DomainWarp,   "domain_warp",  DomainWarpParams, DimSupport::D2D3),
    (Combinator,   "combinator",   CombinatorParams, DimSupport::D2D3D4),
    (Utility,      "utility",      UtilityParams,   DimSupport::D2D3D4),
    (White,        "white",        SeedParams,      DimSupport::All),
}

/// Default persistence values, one per fractal-family algorithm (all four
/// share the same [`FractalParams`] shape but differ in their default
/// `persistence`).
pub const DEFAULT_PERSISTENCE_FBM_BILLOW: f64 = 0.5;
/// Deliberately 0.5, not 1.0: callers wanting the noise-crate library
/// default of 1.0 for `ridged_multi` must pass `persistence` explicitly.
pub const DEFAULT_PERSISTENCE_RIDGED: f64 = 0.5;
/// HybridMulti combines octave amplitudes multiplicatively; a lower
/// persistence prevents signal saturation (consistent with noise-crate
/// examples).
pub const DEFAULT_PERSISTENCE_HYBRID: f64 = 0.25;

/// Builds the `AlgorithmParams` value for `name` with all params omitted
/// (i.e. `{}`), the same way `main.rs`'s CLI `--algorithm`/`--params`
/// handling does — reusing `AlgorithmParams`'s tag/content `Deserialize`
/// impl instead of a second per-algorithm constructor.
fn default_algorithm_params(name: &str) -> Option<AlgorithmParams> {
    serde_json::from_value(serde_json::json!({ "algorithm": name, "params": {} })).ok()
}

/// Returns default parameter values for a given algorithm name, for display
/// via `GET /v1/algorithms`.
///
/// This is derived from [`crate::resolve::resolve_params`] — the same
/// resolution logic used for actual generation — rather than a second,
/// independently-maintained name-keyed table, so the advertised defaults
/// can never drift from what generation actually uses. `seed` is nulled out
/// here (rather than echoing the concrete value `resolve_params` randomly
/// generates for a request with no seed) since defaults are meant to show
/// "no seed was requested", not a fabricated one.
pub fn algorithm_defaults(name: &str) -> serde_json::Value {
    let Some(algorithm) = default_algorithm_params(name) else {
        return serde_json::json!({});
    };
    let request = crate::model::GenerateNoiseRequest {
        algorithm,
        sampling: crate::model::Sampling { size: None },
        output: None,
    };
    let mut defaults = crate::resolve::resolve_params(&request).to_json();
    if let Some(obj) = defaults.as_object_mut() {
        if obj.contains_key("seed") {
            obj.insert("seed".to_string(), serde_json::Value::Null);
        }
    }
    defaults
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn algorithm_names_has_15_entries() {
        assert_eq!(ALGORITHM_NAMES.len(), 15);
    }

    #[test]
    fn name_and_dim_support_are_consistent_with_wire_tag() {
        let perlin = AlgorithmParams::Perlin(SeedParams::default());
        assert_eq!(perlin.name(), "perlin");
        assert_eq!(perlin.dim_support(), DimSupport::D2D3);

        let white = AlgorithmParams::White(SeedParams::default());
        assert_eq!(white.name(), "white");
        assert_eq!(white.dim_support(), DimSupport::All);
    }

    #[test]
    fn every_algorithm_name_has_defaults() {
        for name in ALGORITHM_NAMES {
            let defaults = algorithm_defaults(name);
            assert!(defaults.is_object(), "{name} defaults should be an object");
        }
    }

    #[test]
    fn fbm_defaults_match_resolve_params_constants() {
        let defaults = algorithm_defaults("fbm");
        assert!(defaults["seed"].is_null());
        assert_eq!(defaults["octaves"], crate::resolve::DEFAULT_OCTAVES);
        assert_eq!(defaults["frequency"], crate::resolve::DEFAULT_FREQUENCY);
        assert_eq!(defaults["lacunarity"], crate::resolve::DEFAULT_LACUNARITY);
        assert_eq!(defaults["persistence"], DEFAULT_PERSISTENCE_FBM_BILLOW);
    }

    #[test]
    fn ridged_multi_and_hybrid_multi_defaults_have_distinct_persistence() {
        assert_eq!(
            algorithm_defaults("ridged_multi")["persistence"],
            DEFAULT_PERSISTENCE_RIDGED
        );
        assert_eq!(
            algorithm_defaults("hybrid_multi")["persistence"],
            DEFAULT_PERSISTENCE_HYBRID
        );
    }

    #[test]
    fn utility_defaults_have_no_seed_field() {
        // Utility noise is deterministic and takes no seed, unlike every
        // other algorithm family.
        let defaults = algorithm_defaults("utility");
        assert!(defaults.get("seed").is_none());
        assert_eq!(defaults["kind"], "constant");
    }

    #[test]
    fn unknown_algorithm_name_returns_empty_defaults() {
        assert_eq!(
            algorithm_defaults("not-a-real-algorithm"),
            serde_json::json!({})
        );
    }
}
