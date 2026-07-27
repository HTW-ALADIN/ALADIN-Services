//! Axum HTTP handlers. Both handlers are thin adapters over
//! `crate::algorithms`/`crate::service`; no domain logic lives here.

use axum::{http::StatusCode, Json};

use crate::algorithms::{algorithm_defaults, ALGORITHM_NAMES};
use crate::limits::DEFAULT_SAMPLING_SIZE;
use crate::model::{AlgorithmInfo, GenerateNoiseRequest, NoiseFieldResult};
use crate::service;

#[utoipa::path(
    get,
    path = "/v1/algorithms",
    tag = "noise",
    responses(
        (status = 200, description = "List of algorithms with their default parameters", body = Vec<AlgorithmInfo>)
    )
)]
pub async fn list_algorithms() -> Json<Vec<AlgorithmInfo>> {
    let entries: Vec<AlgorithmInfo> = ALGORITHM_NAMES
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
    let algorithm_name = payload.algorithm.name().to_string();
    let field_id = format!("nsf_{}", uuid::Uuid::new_v4());
    // Must match the default `crate::service::generate` uses for the success
    // path, so a rejected request that omitted `sampling.size` echoes the
    // same size the service would actually have used, rather than `[]`.
    let size_for_error = payload
        .sampling_size()
        .unwrap_or_else(|| DEFAULT_SAMPLING_SIZE.to_vec());

    // Run the CPU-bound validation/generation/shaping work on a blocking
    // thread so a large request doesn't stall the async executor for other
    // in-flight requests.
    let result = tokio::task::spawn_blocking(move || service::generate(&payload))
        .await
        .expect("noise generation task panicked");

    match result {
        Ok(field) => (
            StatusCode::CREATED,
            Json(NoiseFieldResult {
                id: field_id,
                status: "completed".to_string(),
                algorithm: algorithm_name,
                data: field.data,
                size: field.size,
                params_used: field.params_used,
            }),
        ),
        Err(err) => {
            let status = err.status_code();
            (
                status,
                Json(err.into_result(field_id, algorithm_name, size_for_error)),
            )
        }
    }
}
