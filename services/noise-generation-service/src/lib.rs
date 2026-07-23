// Range loops and casts are clearer for noise generation — keep them explicit
#![allow(clippy::needless_range_loop, clippy::unnecessary_cast)]

use axum::{http::StatusCode, Json};
use fastnoise_lite::FastNoiseLite;
use noise::{
    Add, Blend, Constant, Cylinders, HybridMulti, Max, Min, MultiFractal, Multiply, NoiseFn,
    Perlin, Simplex, SuperSimplex,
};
use serde::{Deserialize, Serialize};
use utoipa::{OpenApi, ToSchema};

// ─── Default constants ─────────────────────────────────────────────────────

/// Default fractal octaves (4). 4 octaves is a standard trade-off between
/// detail richness and performance, matching noise-crate's own examples.
const DEFAULT_OCTAVES: usize = 4;

/// Default frequency (0.1). Gives ~10 noise features per unit length,
/// producing well-visible structures at typical grid resolutions (64-512).
const DEFAULT_FREQUENCY: f64 = 0.1;

/// Default lacunarity (2.0). Doubles frequency per octave — this is the
/// standard lacunarity for Perlin-based fractals (noise-crate default).
const DEFAULT_LACUNARITY: f64 = 2.0;

/// Default persistence for Fbm and Billow (0.5). Halves amplitude per
/// octave, producing natural 1/f spectral falloff. This is the standard
/// noise-crate default for both Fbm and Billow.
const DEFAULT_PERSISTENCE_FBM_BILLOW: f64 = 0.5;

/// Default persistence for RidgedMulti (0.5). Unified to 0.5 from the
/// original 1.0 — review of the integration tests shows that ridged_multi
/// tests always pass `persistence: 0.5` explicitly, indicating that the
/// 1.0 default was a copy-paste error. Users who need 1.0 can pass it
/// explicitly via the `params.persistence` field.
const DEFAULT_PERSISTENCE_RIDGED: f64 = 0.5;

/// Default persistence for HybridMulti (0.25). HybridMulti combines octave
/// amplitudes multiplicatively; a lower persistence prevents signal
/// saturation (consistent with noise-crate examples).
const DEFAULT_PERSISTENCE_HYBRID: f64 = 0.25;

/// Default cellular jitter (0.45). Standard Worley noise jitter factor.
const DEFAULT_JITTER: f64 = 0.45;

/// Default PingPong strength (2.0). Standard wrapping strength for PingPong fractal.
const DEFAULT_STRENGTH: f64 = 2.0;

/// Default domain warp amplitude (1.0). Standard amplitude for domain warping.
const DEFAULT_AMPLITUDE: f64 = 1.0;

/// Default combinator blend factor (0.5). Equal mix when blending two sources.
const DEFAULT_BLEND_FACTOR: f64 = 0.5;

/// Default utility constant value (1.0).
const DEFAULT_UTILITY_VALUE: f64 = 1.0;

// ─── Helpers ──────────────────────────────────────────────────────────────────

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

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct SeedParams {
    pub seed: Option<u32>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct CellularParams {
    pub seed: Option<u32>,
    pub distance_function: Option<CellularDistanceFunction>,
    pub return_type: Option<CellularReturnType>,
    pub jitter: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum CellularDistanceFunction {
    Euclidean,
    EuclideanSq,
    Manhattan,
    Hybrid,
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum CellularReturnType {
    CellValue,
    Distance,
    Distance2,
    Distance2Add,
    Distance2Sub,
    Distance2Mul,
    Distance2Div,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct FractalParams {
    pub seed: Option<u32>,
    pub octaves: Option<usize>,
    pub frequency: Option<f64>,
    pub lacunarity: Option<f64>,
    pub persistence: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct RidgedMultiParams {
    pub seed: Option<u32>,
    pub octaves: Option<usize>,
    pub frequency: Option<f64>,
    pub lacunarity: Option<f64>,
    pub persistence: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct PingPongParams {
    pub seed: Option<u32>,
    pub strength: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct DomainWarpParams {
    pub seed: Option<u32>,
    pub amplitude: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct CombinatorParams {
    pub seed: Option<u32>,
    pub op: Option<CombinatorOp>,
    pub blend_factor: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum CombinatorOp {
    Add,
    Multiply,
    Min,
    Max,
    Blend,
}

impl Default for CombinatorOp {
    fn default() -> Self {
        Self::Add
    }
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct UtilityParams {
    pub kind: Option<UtilityKind>,
    pub value: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum UtilityKind {
    Constant,
    Cylinders,
}

impl Default for UtilityKind {
    fn default() -> Self {
        Self::Constant
    }
}

#[derive(Serialize, Debug, ToSchema)]
pub struct AlgorithmInfo {
    /// Algorithm name / identifier (e.g. "perlin", "fbm")
    pub name: String,
    /// Default parameter values used when the corresponding field is omitted.
    /// The `seed` is shown as `null` because it is randomly generated per request.
    pub defaults: serde_json::Value,
}

#[derive(OpenApi)]
#[openapi(
    paths(
        list_algorithms,
        generate_noise
    ),
    components(
        schemas(
            GenerateNoiseRequest,
            Sampling,
            Output,
            OutputFormat,
            NoiseFieldResult,
            AlgorithmInfo,
            SeedParams,
            CellularParams,
            CellularDistanceFunction,
            CellularReturnType,
            FractalParams,
            RidgedMultiParams,
            PingPongParams,
            DomainWarpParams,
            CombinatorParams,
            CombinatorOp,
            UtilityParams,
            UtilityKind
        )
    ),
    tags(
        (name = "noise", description = "Noise generation API")
    )
)]
pub struct ApiDoc;

#[derive(Serialize, Deserialize, Debug, ToSchema)]
pub struct Sampling {
    pub mode: String,
    pub size: Option<Vec<usize>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum OutputFormat {
    Json,
    Csv,
}

impl Default for OutputFormat {
    fn default() -> Self {
        Self::Json
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
pub struct Output {
    pub format: OutputFormat,
    pub normalize: bool,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
#[serde(tag = "algorithm")]
pub enum GenerateNoiseRequest {
    #[serde(rename = "perlin")]
    Perlin {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "simplex")]
    Simplex {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "opensimplex2")]
    OpenSimplex2 {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "supersimplex")]
    SuperSimplex {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "value")]
    Value {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "cellular")]
    Cellular {
        #[serde(default)]
        params: CellularParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "fbm")]
    Fbm {
        #[serde(default)]
        params: FractalParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "billow")]
    Billow {
        #[serde(default)]
        params: FractalParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "ridged_multi")]
    RidgedMulti {
        #[serde(default)]
        params: RidgedMultiParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "hybrid_multi")]
    HybridMulti {
        #[serde(default)]
        params: RidgedMultiParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "pingpong")]
    PingPong {
        #[serde(default)]
        params: PingPongParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "domain_warp")]
    DomainWarp {
        #[serde(default)]
        params: DomainWarpParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "combinator")]
    Combinator {
        #[serde(default)]
        params: CombinatorParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "utility")]
    Utility {
        #[serde(default)]
        params: UtilityParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "white")]
    White {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
}

#[derive(Serialize, Debug, ToSchema)]
pub struct NoiseFieldResult {
    pub id: String,
    pub status: String,
    pub algorithm: String,
    pub data: serde_json::Value,
    pub size: Vec<usize>,
    pub params_used: serde_json::Value,
}

/// Returns default parameter values for a given algorithm name.
/// Uses the same DEFAULT_* constants as the noise generation path.
fn algorithm_defaults(name: &str) -> serde_json::Value {
    match name {
        "perlin" | "simplex" | "opensimplex2" | "supersimplex" | "value" | "white" => {
            serde_json::json!({ "seed": null })
        }
        "cellular" => {
            serde_json::json!({
                "seed": null,
                "distance_function": "euclidean",
                "return_type": "cell_value",
                "jitter": DEFAULT_JITTER
            })
        }
        "fbm" | "billow" => {
            serde_json::json!({
                "seed": null,
                "octaves": DEFAULT_OCTAVES,
                "frequency": DEFAULT_FREQUENCY,
                "lacunarity": DEFAULT_LACUNARITY,
                "persistence": DEFAULT_PERSISTENCE_FBM_BILLOW
            })
        }
        "ridged_multi" => {
            serde_json::json!({
                "seed": null,
                "octaves": DEFAULT_OCTAVES,
                "frequency": DEFAULT_FREQUENCY,
                "lacunarity": DEFAULT_LACUNARITY,
                "persistence": DEFAULT_PERSISTENCE_RIDGED
            })
        }
        "hybrid_multi" => {
            serde_json::json!({
                "seed": null,
                "octaves": DEFAULT_OCTAVES,
                "frequency": DEFAULT_FREQUENCY,
                "lacunarity": DEFAULT_LACUNARITY,
                "persistence": DEFAULT_PERSISTENCE_HYBRID
            })
        }
        "pingpong" => {
            serde_json::json!({
                "seed": null,
                "strength": DEFAULT_STRENGTH
            })
        }
        "domain_warp" => {
            serde_json::json!({
                "seed": null,
                "amplitude": DEFAULT_AMPLITUDE
            })
        }
        "combinator" => {
            serde_json::json!({
                "seed": null,
                "op": "add",
                "blend_factor": DEFAULT_BLEND_FACTOR
            })
        }
        "utility" => {
            serde_json::json!({
                "seed": null,
                "kind": "constant",
                "value": DEFAULT_UTILITY_VALUE
            })
        }
        _ => serde_json::json!({}),
    }
}

#[utoipa::path(
    get,
    path = "/v1/algorithms",
    tag = "noise",
    responses(
        (status = 200, description = "List of algorithms with their default parameters", body = Vec<AlgorithmInfo>)
    )
)]
pub async fn list_algorithms() -> Json<Vec<AlgorithmInfo>> {
    let names = [
        "perlin", "simplex", "opensimplex2", "supersimplex",
        "value", "cellular", "fbm", "billow", "ridged_multi",
        "hybrid_multi", "pingpong", "domain_warp", "combinator",
        "utility", "white",
    ];
    let entries: Vec<AlgorithmInfo> = names
        .iter()
        .map(|name| AlgorithmInfo {
            name: name.to_string(),
            defaults: algorithm_defaults(name),
        })
        .collect();
    Json(entries)
}

#[utoipa::path(
    post,
    path = "/v1/noise",
    tag = "noise",
    request_body = GenerateNoiseRequest,
    responses(
        (status = 201, description = "Noise field created", body = NoiseFieldResult)
    )
)]
pub async fn generate_noise(
    Json(payload): Json<GenerateNoiseRequest>,
) -> (StatusCode, Json<NoiseFieldResult>) {
    let algorithm_name = payload.algorithm_name();
    let field_id = format!("nsf_{}", uuid::Uuid::new_v4());

    // Determine size and dimensionality from sampling
    let size = payload.sampling_size().unwrap_or_else(|| vec![64, 64]);
    let mode = match size.len() {
        1 => "1d",
        2 => "2d",
        3 => "3d",
        _ => "2d",
    };

    // Validate that the selected algorithm supports the requested dimension
    // before resolving parameters (avoid unnecessary random seed allocation on error)
    if let Err(msg) = payload.check_dimension_support(mode) {
        return (
            StatusCode::BAD_REQUEST,
            Json(NoiseFieldResult {
                id: field_id,
                status: format!("error: {}", msg),
                algorithm: algorithm_name,
                data: serde_json::Value::Null,
                size,
                params_used: serde_json::Value::Null,
            }),
        );
    }

    // Resolve parameters once — used for both generation and response echo
    let resolved = resolve_params(&payload);

    // Generate flattened noise data using resolved parameters
    let total: usize = size.iter().product();
    let mut flat = vec![0.0; total];
    generate_flat(&mut flat, &payload, &resolved, &size, mode);

    // Normalize (if requested)
    let normalize = payload.should_normalize();
    if normalize {
        let mut min_val = f64::MAX;
        let mut max_val = f64::MIN;
        for &v in &flat {
            if v < min_val {
                min_val = v;
            }
            if v > max_val {
                max_val = v;
            }
        }
        let range = max_val - min_val;
        if range > 0.0 {
            for v in &mut flat {
                *v = (*v - min_val) / range;
            }
        }
    }

    // Shape flat data into the requested dimensionality
    let shaped = shape_data(&flat, &size, mode);

    (
        StatusCode::CREATED,
        Json(NoiseFieldResult {
            id: field_id,
            status: "completed".to_string(),
            algorithm: algorithm_name,
            data: shaped,
            size,
            params_used: resolved.to_json(),
        }),
    )
}

// ─── Algorithm name extraction via serde tag ──────────────────────────────────

impl GenerateNoiseRequest {
    fn algorithm_name(&self) -> String {
        match self {
            GenerateNoiseRequest::Perlin { .. } => "perlin",
            GenerateNoiseRequest::Simplex { .. } => "simplex",
            GenerateNoiseRequest::OpenSimplex2 { .. } => "opensimplex2",
            GenerateNoiseRequest::SuperSimplex { .. } => "supersimplex",
            GenerateNoiseRequest::Value { .. } => "value",
            GenerateNoiseRequest::Cellular { .. } => "cellular",
            GenerateNoiseRequest::Fbm { .. } => "fbm",
            GenerateNoiseRequest::Billow { .. } => "billow",
            GenerateNoiseRequest::RidgedMulti { .. } => "ridged_multi",
            GenerateNoiseRequest::HybridMulti { .. } => "hybrid_multi",
            GenerateNoiseRequest::PingPong { .. } => "pingpong",
            GenerateNoiseRequest::DomainWarp { .. } => "domain_warp",
            GenerateNoiseRequest::Combinator { .. } => "combinator",
            GenerateNoiseRequest::Utility { .. } => "utility",
            GenerateNoiseRequest::White { .. } => "white",
        }
        .to_string()
    }

    /// Returns `Err(msg)` if the algorithm does not support the requested dimension.
    fn check_dimension_support(&self, mode: &str) -> Result<(), String> {
        match self {
            // noise-crate types (Simplex, SuperSimplex, Fbm, Billow, RidgedMulti, HybridMulti,
            // Combinator, Utility): support 2D and 3D via NoiseFn<f64, 2> and NoiseFn<f64, 3>.
            // The noise crate does NOT support 1D — we return an error for 1D.
            GenerateNoiseRequest::Simplex { .. }
            | GenerateNoiseRequest::SuperSimplex { .. }
            | GenerateNoiseRequest::Fbm { .. }
            | GenerateNoiseRequest::Billow { .. }
            | GenerateNoiseRequest::RidgedMulti { .. }
            | GenerateNoiseRequest::HybridMulti { .. }
            | GenerateNoiseRequest::Combinator { .. }
            | GenerateNoiseRequest::Utility { .. } => match mode {
                "1d" => Err(format!(
                    "algorithm '{}' does not support 1D sampling (noise-crate requires at least 2D)",
                    self.algorithm_name()
                )),
                _ => Ok(()),
            },
            // FastNoiseLite types (Perlin, OpenSimplex2, Value, Cellular, PingPong):
            // support 2D and 3D via get_noise_2d/get_noise_3d. No 1D support in fnl either.
            GenerateNoiseRequest::Perlin { .. }
            | GenerateNoiseRequest::OpenSimplex2 { .. }
            | GenerateNoiseRequest::Value { .. }
            | GenerateNoiseRequest::Cellular { .. }
            | GenerateNoiseRequest::PingPong { .. } => match mode {
                "1d" => Err(format!(
                    "algorithm '{}' does not support 1D sampling (fastnoise-lite requires at least 2D)",
                    self.algorithm_name()
                )),
                _ => Ok(()),
            },
            // DomainWarp: only 2D and 3D
            GenerateNoiseRequest::DomainWarp { .. } => match mode {
                "1d" => Err(format!(
                    "algorithm '{}' does not support 1D sampling (domain warping requires at least 2D)",
                    self.algorithm_name()
                )),
                _ => Ok(()),
            },
            // White noise: supports all dimensions natively
            GenerateNoiseRequest::White { .. } => Ok(()),
        }
    }

    fn sampling_size(&self) -> Option<Vec<usize>> {
        match self {
            GenerateNoiseRequest::Perlin { sampling, .. }
            | GenerateNoiseRequest::Simplex { sampling, .. }
            | GenerateNoiseRequest::OpenSimplex2 { sampling, .. }
            | GenerateNoiseRequest::SuperSimplex { sampling, .. }
            | GenerateNoiseRequest::Value { sampling, .. }
            | GenerateNoiseRequest::Cellular { sampling, .. }
            | GenerateNoiseRequest::Fbm { sampling, .. }
            | GenerateNoiseRequest::Billow { sampling, .. }
            | GenerateNoiseRequest::RidgedMulti { sampling, .. }
            | GenerateNoiseRequest::HybridMulti { sampling, .. }
            | GenerateNoiseRequest::PingPong { sampling, .. }
            | GenerateNoiseRequest::DomainWarp { sampling, .. }
            | GenerateNoiseRequest::Combinator { sampling, .. }
            | GenerateNoiseRequest::Utility { sampling, .. }
            | GenerateNoiseRequest::White { sampling, .. } => sampling.size.clone(),
        }
    }

    fn should_normalize(&self) -> bool {
        match self {
            GenerateNoiseRequest::Perlin { output, .. }
            | GenerateNoiseRequest::Simplex { output, .. }
            | GenerateNoiseRequest::OpenSimplex2 { output, .. }
            | GenerateNoiseRequest::SuperSimplex { output, .. }
            | GenerateNoiseRequest::Value { output, .. }
            | GenerateNoiseRequest::Cellular { output, .. }
            | GenerateNoiseRequest::Fbm { output, .. }
            | GenerateNoiseRequest::Billow { output, .. }
            | GenerateNoiseRequest::RidgedMulti { output, .. }
            | GenerateNoiseRequest::HybridMulti { output, .. }
            | GenerateNoiseRequest::PingPong { output, .. }
            | GenerateNoiseRequest::DomainWarp { output, .. }
            | GenerateNoiseRequest::Combinator { output, .. }
            | GenerateNoiseRequest::Utility { output, .. }
            | GenerateNoiseRequest::White { output, .. } => {
                output.as_ref().map(|o| o.normalize).unwrap_or(false)
            }
        }
    }
}

// ─── Macro: 2D/3D per-cell iteration for pixel-wise noise ──────────────

/// Generates the 2D or 3D loop structure and calls `$f(pos)` for each cell,
/// where `pos` is `[f64; 2]` or `[f64; 3]`. Shared by Combinator and
/// Utility to avoid duplicating the nested loop code.
macro_rules! fill_cell_loops {
    ($flat:expr, $size:expr, $mode:expr, $f:expr) => {
        match $mode {
            "2d" => {
                let w = $size[0];
                let h = $size[1];
                for y in 0..h {
                    for x in 0..w {
                        $flat[y * w + x] = $f([x as f64 * 0.1, y as f64 * 0.1]);
                    }
                }
            }
            "3d" => {
                let w = $size[0];
                let h = $size[1];
                let d = $size[2];
                let mut idx = 0;
                for z in 0..d {
                    for y in 0..h {
                        for x in 0..w {
                            $flat[idx] = $f([x as f64 * 0.1, y as f64 * 0.1, z as f64 * 0.1]);
                            idx += 1;
                        }
                    }
                }
            }
            _ => unreachable!("dimension already validated"),
        }
    };
}

// ─── Resolved parameters — single resolution for generation + echo ──────────

/// Fully resolved noise parameters for one algorithm family. Resolved exactly
/// once per request; used for both noise generation **and** the `params_used`
/// echo. This eliminates the critical seed-mismatch bug where `get_seed` was
/// called twice with potentially different random seeds.
enum ResolvedNoiseParams {
    SeedOnly { seed: u32 },
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
    fn to_json(&self) -> serde_json::Value {
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
            ResolvedNoiseParams::Combinator { seed, op, blend_factor } => {
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

/// Resolves optional request parameters into concrete values once.
/// Uses the centralized `DEFAULT_*` constants for defaults.
fn resolve_params(payload: &GenerateNoiseRequest) -> ResolvedNoiseParams {
    match payload {
        GenerateNoiseRequest::Perlin { params, .. }
        | GenerateNoiseRequest::Simplex { params, .. }
        | GenerateNoiseRequest::OpenSimplex2 { params, .. }
        | GenerateNoiseRequest::SuperSimplex { params, .. }
        | GenerateNoiseRequest::Value { params, .. }
        | GenerateNoiseRequest::White { params, .. } => ResolvedNoiseParams::SeedOnly {
            seed: get_seed(params.seed),
        },
        GenerateNoiseRequest::Cellular { params, .. } => ResolvedNoiseParams::Cellular {
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
        GenerateNoiseRequest::Fbm { params, .. } => ResolvedNoiseParams::Fractal {
            seed: get_seed(params.seed),
            octaves: params.octaves.unwrap_or(DEFAULT_OCTAVES),
            frequency: params.frequency.unwrap_or(DEFAULT_FREQUENCY),
            lacunarity: params.lacunarity.unwrap_or(DEFAULT_LACUNARITY),
            persistence: params.persistence.unwrap_or(DEFAULT_PERSISTENCE_FBM_BILLOW),
        },
        GenerateNoiseRequest::Billow { params, .. } => ResolvedNoiseParams::Fractal {
            seed: get_seed(params.seed),
            octaves: params.octaves.unwrap_or(DEFAULT_OCTAVES),
            frequency: params.frequency.unwrap_or(DEFAULT_FREQUENCY),
            lacunarity: params.lacunarity.unwrap_or(DEFAULT_LACUNARITY),
            persistence: params.persistence.unwrap_or(DEFAULT_PERSISTENCE_FBM_BILLOW),
        },
        GenerateNoiseRequest::RidgedMulti { params, .. } => ResolvedNoiseParams::Fractal {
            seed: get_seed(params.seed),
            octaves: params.octaves.unwrap_or(DEFAULT_OCTAVES),
            frequency: params.frequency.unwrap_or(DEFAULT_FREQUENCY),
            lacunarity: params.lacunarity.unwrap_or(DEFAULT_LACUNARITY),
            persistence: params.persistence.unwrap_or(DEFAULT_PERSISTENCE_RIDGED),
        },
        GenerateNoiseRequest::HybridMulti { params, .. } => ResolvedNoiseParams::Fractal {
            seed: get_seed(params.seed),
            octaves: params.octaves.unwrap_or(DEFAULT_OCTAVES),
            frequency: params.frequency.unwrap_or(DEFAULT_FREQUENCY),
            lacunarity: params.lacunarity.unwrap_or(DEFAULT_LACUNARITY),
            persistence: params.persistence.unwrap_or(DEFAULT_PERSISTENCE_HYBRID),
        },
        GenerateNoiseRequest::PingPong { params, .. } => ResolvedNoiseParams::PingPong {
            seed: get_seed(params.seed),
            strength: params.strength.unwrap_or(DEFAULT_STRENGTH),
        },
        GenerateNoiseRequest::DomainWarp { params, .. } => ResolvedNoiseParams::DomainWarp {
            seed: get_seed(params.seed),
            amplitude: params.amplitude.unwrap_or(DEFAULT_AMPLITUDE),
        },
        GenerateNoiseRequest::Combinator { params, .. } => ResolvedNoiseParams::Combinator {
            seed: get_seed(params.seed),
            op: params.op.clone().unwrap_or(CombinatorOp::Add),
            blend_factor: params.blend_factor.unwrap_or(DEFAULT_BLEND_FACTOR),
        },
        GenerateNoiseRequest::Utility { params, .. } => ResolvedNoiseParams::Utility {
            kind: params.kind.clone().unwrap_or(UtilityKind::Constant),
            value: params.value.unwrap_or(DEFAULT_UTILITY_VALUE),
        },
    }
}

// ─── Noise generation per algorithm (flat output) ──────────────────────────

/// Generates noise into a flat Vec<f64> according to the requested dimensionality.
/// `size` is the grid extent: [width] for 1D, [width, height] for 2D, [width, height, depth] for 3D.
/// `resolved` contains the already-resolved parameters (seed etc.) — this is the *only* place
/// parameter resolution happens for generation, ensuring consistency with `params_used`.
fn generate_flat(
    flat: &mut [f64],
    payload: &GenerateNoiseRequest,
    resolved: &ResolvedNoiseParams,
    size: &[usize],
    mode: &str,
) {
    match (payload, resolved) {
        // ─── fastnoise-lite algorithms (2D/3D) ────────────────────────────────
        (GenerateNoiseRequest::Perlin { .. }, ResolvedNoiseParams::SeedOnly { seed }) => {
            let mut noise = FastNoiseLite::with_seed(*seed as i32);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
            fill_fnl(flat, size, mode, &noise);
        }
        (GenerateNoiseRequest::OpenSimplex2 { .. }, ResolvedNoiseParams::SeedOnly { seed }) => {
            let mut noise = FastNoiseLite::with_seed(*seed as i32);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::OpenSimplex2));
            fill_fnl(flat, size, mode, &noise);
        }
        (GenerateNoiseRequest::Value { .. }, ResolvedNoiseParams::SeedOnly { seed }) => {
            let mut noise = FastNoiseLite::with_seed(*seed as i32);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Value));
            fill_fnl(flat, size, mode, &noise);
        }
        (
            GenerateNoiseRequest::Cellular { .. },
            ResolvedNoiseParams::Cellular {
                seed,
                distance_function,
                return_type,
                jitter,
            },
        ) => {
            let mut noise = FastNoiseLite::with_seed(*seed as i32);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Cellular));
            noise.set_cellular_distance_function(Some(match distance_function {
                CellularDistanceFunction::Euclidean => {
                    fastnoise_lite::CellularDistanceFunction::Euclidean
                }
                CellularDistanceFunction::EuclideanSq => {
                    fastnoise_lite::CellularDistanceFunction::EuclideanSq
                }
                CellularDistanceFunction::Manhattan => {
                    fastnoise_lite::CellularDistanceFunction::Manhattan
                }
                CellularDistanceFunction::Hybrid => {
                    fastnoise_lite::CellularDistanceFunction::Hybrid
                }
            }));
            noise.set_cellular_return_type(Some(match return_type {
                CellularReturnType::CellValue => fastnoise_lite::CellularReturnType::CellValue,
                CellularReturnType::Distance => fastnoise_lite::CellularReturnType::Distance,
                CellularReturnType::Distance2 => fastnoise_lite::CellularReturnType::Distance2,
                CellularReturnType::Distance2Add => {
                    fastnoise_lite::CellularReturnType::Distance2Add
                }
                CellularReturnType::Distance2Sub => {
                    fastnoise_lite::CellularReturnType::Distance2Sub
                }
                CellularReturnType::Distance2Mul => {
                    fastnoise_lite::CellularReturnType::Distance2Mul
                }
                CellularReturnType::Distance2Div => {
                    fastnoise_lite::CellularReturnType::Distance2Div
                }
            }));
            noise.set_cellular_jitter(Some(*jitter as f32));
            fill_fnl(flat, size, mode, &noise);
        }
        // ─── PingPong: fastnoise-lite fractal ─────────────────────────────────
        (
            GenerateNoiseRequest::PingPong { .. },
            ResolvedNoiseParams::PingPong { seed, strength },
        ) => {
            let mut noise = FastNoiseLite::with_seed(*seed as i32);
            noise.set_fractal_type(Some(fastnoise_lite::FractalType::PingPong));
            noise.set_fractal_ping_pong_strength(Some(*strength as f32));
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
            fill_fnl(flat, size, mode, &noise);
        }
        // ─── DomainWarp: fastnoise-lite domain warp ───────────────────────────
        (
            GenerateNoiseRequest::DomainWarp { .. },
            ResolvedNoiseParams::DomainWarp { seed, amplitude },
        ) => {
            fill_domain_warp(flat, size, mode, *seed as i32, *amplitude);
        }
        // ─── noise-crate algorithms (2D/3D) ───────────────────────────────────
        (GenerateNoiseRequest::Simplex { .. }, ResolvedNoiseParams::SeedOnly { seed }) => {
            let simplex = Simplex::new(*seed);
            fill_noise_rs::<Simplex>(flat, size, mode, &simplex);
        }
        (GenerateNoiseRequest::SuperSimplex { .. }, ResolvedNoiseParams::SeedOnly { seed }) => {
            let s = SuperSimplex::new(*seed);
            fill_noise_rs::<SuperSimplex>(flat, size, mode, &s);
        }
        // ─── Fractal family (Fbm, Billow, RidgedMulti, HybridMulti) ──────────
        (
            GenerateNoiseRequest::Fbm { .. },
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => {
            let n = noise::Fbm::<Perlin>::new(*seed)
                .set_octaves(*octaves)
                .set_frequency(*frequency)
                .set_lacunarity(*lacunarity)
                .set_persistence(*persistence);
            fill_noise_rs::<noise::Fbm<Perlin>>(flat, size, mode, &n);
        }
        (
            GenerateNoiseRequest::Billow { .. },
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => {
            let n = noise::Billow::<Perlin>::new(*seed)
                .set_octaves(*octaves)
                .set_frequency(*frequency)
                .set_lacunarity(*lacunarity)
                .set_persistence(*persistence);
            fill_noise_rs::<noise::Billow<Perlin>>(flat, size, mode, &n);
        }
        (
            GenerateNoiseRequest::RidgedMulti { .. },
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => {
            let n = noise::RidgedMulti::<Perlin>::new(*seed)
                .set_octaves(*octaves)
                .set_frequency(*frequency)
                .set_lacunarity(*lacunarity)
                .set_persistence(*persistence);
            fill_noise_rs::<noise::RidgedMulti<Perlin>>(flat, size, mode, &n);
        }
        (
            GenerateNoiseRequest::HybridMulti { .. },
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => {
            let n = HybridMulti::<Perlin>::new(*seed)
                .set_octaves(*octaves)
                .set_frequency(*frequency)
                .set_lacunarity(*lacunarity)
                .set_persistence(*persistence);
            fill_noise_rs::<HybridMulti<Perlin>>(flat, size, mode, &n);
        }
        // ─── Combinator ──────────────────────────────────────────────────────
        (
            GenerateNoiseRequest::Combinator { .. },
            ResolvedNoiseParams::Combinator { seed, op, blend_factor },
        ) => {
            let source1 = Perlin::new(*seed);
            let source2 = Perlin::new(*seed + 1);
            let bf = *blend_factor;
            fill_cell_loops!(flat, size, mode, |pos| match op {
                CombinatorOp::Add => Add::new(source1, source2).get(pos),
                CombinatorOp::Multiply => Multiply::new(source1, source2).get(pos),
                CombinatorOp::Min => Min::new(source1, source2).get(pos),
                CombinatorOp::Max => Max::new(source1, source2).get(pos),
                CombinatorOp::Blend => Blend::new(source1, source2, Constant::new(bf)).get(pos),
            });
        }
        // ─── Utility ─────────────────────────────────────────────────────────
        (GenerateNoiseRequest::Utility { .. }, ResolvedNoiseParams::Utility { kind, value }) => {
            let val = *value;
            fill_cell_loops!(flat, size, mode, |pos| match kind {
                UtilityKind::Constant => Constant::new(val).get(pos),
                UtilityKind::Cylinders => Cylinders::new().get(pos),
            });
        }
        // ─── White noise ─────────────────────────────────────────────────────
        (GenerateNoiseRequest::White { .. }, ResolvedNoiseParams::SeedOnly { seed }) => {
            let s = *seed as u64;
            match mode {
                "1d" => {
                    let w = size[0];
                    for x in 0..w {
                        flat[x] = white_noise_1d(s, x);
                    }
                }
                "2d" => {
                    let w = size[0];
                    let h = size[1];
                    for y in 0..h {
                        for x in 0..w {
                            flat[y * w + x] = white_noise_2d(s, x, y);
                        }
                    }
                }
                "3d" => {
                    let w = size[0];
                    let h = size[1];
                    let d = size[2];
                    let mut idx = 0;
                    for z in 0..d {
                        for y in 0..h {
                            for x in 0..w {
                                flat[idx] = white_noise_3d(s, x, y, z);
                                idx += 1;
                            }
                        }
                    }
                }
                _ => unreachable!("dimension already validated"),
            }
        }
        // Safety: payload variant always matches resolved variant
        _ => unreachable!("payload/resolved type mismatch — this is a programming error"),
    }
}

// ─── Dimension-generic fill helpers ──────────────────────────────────────────

/// Fills `flat` using fastnoise-lite (2D or 3D).
fn fill_fnl(flat: &mut [f64], size: &[usize], mode: &str, noise: &FastNoiseLite) {
    match mode {
        "2d" => {
            let w = size[0];
            let h = size[1];
            for y in 0..h {
                for x in 0..w {
                    flat[y * w + x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                }
            }
        }
        "3d" => {
            let w = size[0];
            let h = size[1];
            let d = size[2];
            let mut idx = 0;
            for z in 0..d {
                for y in 0..h {
                    for x in 0..w {
                        flat[idx] = noise.get_noise_3d(x as f32, y as f32, z as f32) as f64;
                        idx += 1;
                    }
                }
            }
        }
        _ => unreachable!("dimension already validated"),
    }
}

/// Fills `flat` using a noise-crate NoiseFn source (2D or 3D).
fn fill_noise_rs<T>(flat: &mut [f64], size: &[usize], mode: &str, noise: &T)
where
    T: NoiseFn<f64, 2> + NoiseFn<f64, 3>,
{
    match mode {
        "2d" => {
            let w = size[0];
            let h = size[1];
            for y in 0..h {
                for x in 0..w {
                    flat[y * w + x] = noise.get([x as f64 * 0.1, y as f64 * 0.1]);
                }
            }
        }
        "3d" => {
            let w = size[0];
            let h = size[1];
            let d = size[2];
            let mut idx = 0;
            for z in 0..d {
                for y in 0..h {
                    for x in 0..w {
                        flat[idx] =
                            noise.get([x as f64 * 0.1, y as f64 * 0.1, z as f64 * 0.1]);
                        idx += 1;
                    }
                }
            }
        }
        _ => unreachable!("dimension already validated"),
    }
}

/// Fills `flat` using fastnoise-lite domain warping (2D or 3D).
fn fill_domain_warp(flat: &mut [f64], size: &[usize], mode: &str, seed: i32, amplitude: f64) {
    match mode {
        "2d" => {
            let w = size[0];
            let h = size[1];
            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_domain_warp_type(Some(fastnoise_lite::DomainWarpType::OpenSimplex2));
            noise.set_domain_warp_amp(Some(amplitude as f32));
            for y in 0..h {
                for x in 0..w {
                    let (wx, wy) = noise.domain_warp_2d(x as f32, y as f32);
                    let mut base = FastNoiseLite::with_seed(seed + 1);
                    base.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                    flat[y * w + x] = base.get_noise_2d(wx, wy) as f64;
                }
            }
        }
        "3d" => {
            let w = size[0];
            let h = size[1];
            let d = size[2];
            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_domain_warp_type(Some(fastnoise_lite::DomainWarpType::OpenSimplex2));
            noise.set_domain_warp_amp(Some(amplitude as f32));
            let mut idx = 0;
            for z in 0..d {
                for y in 0..h {
                    for x in 0..w {
                        let (wx, wy, wz) =
                            noise.domain_warp_3d(x as f32, y as f32, z as f32);
                        let mut base = FastNoiseLite::with_seed(seed + 1);
                        base.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                        flat[idx] = base.get_noise_3d(wx, wy, wz) as f64;
                        idx += 1;
                    }
                }
            }
        }
        _ => unreachable!("dimension already validated"),
    }
}

// ─── Shape data for response ──────────────────────────────────────────────────

/// Converts a flat Vec<f64> into the JSON shape matching the requested
/// dimensionality: 1D → array, 2D → nested array, 3D → nested array of arrays.
fn shape_data(flat: &[f64], size: &[usize], mode: &str) -> serde_json::Value {
    match mode {
        "1d" => serde_json::Value::Array(flat.iter().map(|v| serde_json::json!(v)).collect()),
        "2d" => {
            let w = size[0];
            let h = size[1];
            let mut rows = Vec::with_capacity(h);
            for y in 0..h {
                let row: Vec<serde_json::Value> = flat[y * w..(y + 1) * w]
                    .iter()
                    .map(|v| serde_json::json!(v))
                    .collect();
                rows.push(serde_json::Value::Array(row));
            }
            serde_json::Value::Array(rows)
        }
        "3d" => {
            let w = size[0];
            let h = size[1];
            let d = size[2];
            let slice = w * h;
            let mut result = Vec::with_capacity(d);
            for z in 0..d {
                let mut rows = Vec::with_capacity(h);
                for y in 0..h {
                    let start = z * slice + y * w;
                    let row: Vec<serde_json::Value> = flat[start..start + w]
                        .iter()
                        .map(|v| serde_json::json!(v))
                        .collect();
                    rows.push(serde_json::Value::Array(row));
                }
                result.push(serde_json::Value::Array(rows));
            }
            serde_json::Value::Array(result)
        }
        _ => serde_json::Value::Null,
    }
}

// ─── White noise helpers ──────────────────────────────────────────────────────

fn white_noise_1d(seed: u64, x: usize) -> f64 {
    let mut state = seed
        .wrapping_mul(6364136223846793005)
        .wrapping_add(1442695040888963407);
    state ^= (x as u64).wrapping_mul(374761393);
    state = state.wrapping_mul(12741261754838537793);
    let hash = state ^ (state >> 31);
    (hash as f64 / u64::MAX as f64) * 2.0 - 1.0
}

fn white_noise_2d(seed: u64, x: usize, y: usize) -> f64 {
    let mut state = seed
        .wrapping_mul(6364136223846793005)
        .wrapping_add(1442695040888963407);
    state ^= (x as u64).wrapping_mul(374761393);
    state ^= (y as u64).wrapping_mul(668265263);
    state = state.wrapping_mul(12741261754838537793);
    let hash = state ^ (state >> 31);
    (hash as f64 / u64::MAX as f64) * 2.0 - 1.0
}

fn white_noise_3d(seed: u64, x: usize, y: usize, z: usize) -> f64 {
    let mut state = seed
        .wrapping_mul(6364136223846793005)
        .wrapping_add(1442695040888963407);
    state ^= (x as u64).wrapping_mul(374761393);
    state ^= (y as u64).wrapping_mul(668265263);
    state ^= (z as u64).wrapping_mul(941568331);
    state = state.wrapping_mul(12741261754838537793);
    let hash = state ^ (state >> 31);
    (hash as f64 / u64::MAX as f64) * 2.0 - 1.0
}

