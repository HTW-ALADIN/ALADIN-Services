//! OpenAPI schema registration.
//!
//! `utoipa` requires every schema type referenced (directly or transitively)
//! by the HTTP API to be listed here manually — adding a new nested type to
//! `crate::model` without adding it to `components(schemas(...))` below will
//! produce an OpenAPI spec with unresolved `$ref`s.

use crate::algorithms::AlgorithmParams;
use crate::http;
use crate::model::{
    AlgorithmInfo, CellularDistanceFunction, CellularParams, CellularReturnType, CombinatorOp,
    CombinatorParams, DomainWarpParams, FractalParams, GenerateNoiseRequest, NoiseFieldResult,
    Output, OutputFormat, PingPongParams, Sampling, SeedParams, UtilityKind, UtilityParams,
};
use utoipa::OpenApi;

#[derive(OpenApi)]
#[openapi(
    paths(
        http::list_algorithms,
        http::generate_noise
    ),
    components(
        schemas(
            GenerateNoiseRequest,
            AlgorithmParams,
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
