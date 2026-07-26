//! Request/response DTOs and per-algorithm parameter structs.
//!
//! `AlgorithmParams`, its wire-name table, and its dimension-support table are
//! defined in [`crate::algorithms`] via a single macro invocation instead of
//! here, so that the set of supported algorithms has exactly one source of
//! truth.

use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

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

/// Shared parameter shape for every noise-crate fractal algorithm (Fbm,
/// Billow, RidgedMulti, HybridMulti). Each algorithm applies its own default
/// `persistence` (see `crate::algorithms::DEFAULT_PERSISTENCE_*`) when the
/// field is omitted; the struct itself is identical across all four, so it is
/// defined once rather than duplicated per algorithm.
#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct FractalParams {
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

#[derive(Serialize, Deserialize, Debug, Clone, Default, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum CombinatorOp {
    #[default]
    Add,
    Multiply,
    Min,
    Max,
    Blend,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct UtilityParams {
    pub kind: Option<UtilityKind>,
    pub value: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum UtilityKind {
    #[default]
    Constant,
    Cylinders,
}

#[derive(Serialize, Debug, ToSchema)]
pub struct AlgorithmInfo {
    /// Algorithm name / identifier (e.g. "perlin", "fbm")
    pub name: String,
    /// Default parameter values used when the corresponding field is omitted.
    /// The `seed` is shown as `null` because it is randomly generated per request.
    pub defaults: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
pub struct Sampling {
    pub size: Option<Vec<usize>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum OutputFormat {
    #[default]
    Json,
    Csv,
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
pub struct Output {
    pub format: OutputFormat,
    pub normalize: bool,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
pub struct GenerateNoiseRequest {
    #[serde(flatten)]
    pub algorithm: crate::algorithms::AlgorithmParams,
    pub sampling: Sampling,
    pub output: Option<Output>,
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

impl GenerateNoiseRequest {
    pub fn sampling_size(&self) -> Option<Vec<usize>> {
        self.sampling.size.clone()
    }

    pub fn should_normalize(&self) -> bool {
        self.output.as_ref().map(|o| o.normalize).unwrap_or(false)
    }

    /// `POST /v1/noise` always returns JSON; CSV is only supported by the CLI's
    /// local `generate` command, which renders it client-side from the JSON body.
    pub fn wants_unsupported_csv(&self) -> bool {
        matches!(
            self.output.as_ref().map(|o| &o.format),
            Some(OutputFormat::Csv)
        )
    }
}
