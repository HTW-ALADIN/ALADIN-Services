use std::{sync::Arc, time::Duration};

use axum::{
    body::Body,
    extract::{DefaultBodyLimit, State},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use utoipa::OpenApi;

#[allow(unused_imports)]
use crate::{error::ProblemDetails, model::RenderResponse};

use crate::{
    config::Limits,
    error::ServiceError,
    model::{
        CapabilitiesResponse, EngineInfo, FeatureInfo, HealthResponse, LimitInfo, RenderRequest,
    },
    openapi::ApiDoc,
    renderer::{self, ENGINE_NAME, ENGINE_VERSION},
};

#[derive(Clone)]
pub struct AppState {
    pub limits: Arc<Limits>,
}

impl AppState {
    pub fn new(limits: Limits) -> Self {
        Self {
            limits: Arc::new(limits),
        }
    }
}

pub fn router(state: AppState) -> Router {
    let body_limit = state.limits.max_body_bytes;
    Router::new()
        .route("/healthz", get(health))
        .route("/v1/capabilities", get(capabilities))
        .route("/v1/render", post(render_template))
        .route("/api-docs/openapi.json", get(openapi_document))
        .layer(DefaultBodyLimit::max(body_limit))
        .with_state(state)
}

#[utoipa::path(
    get,
    path = "/healthz",
    responses((status = 200, description = "Service is healthy", body = HealthResponse))
)]
pub async fn health() -> Json<HealthResponse> {
    Json(HealthResponse { status: "ok" })
}

#[utoipa::path(
    get,
    path = "/v1/capabilities",
    responses((status = 200, description = "Renderer capabilities and active limits", body = CapabilitiesResponse))
)]
pub async fn capabilities(State(state): State<AppState>) -> Json<CapabilitiesResponse> {
    Json(CapabilitiesResponse {
        engine: EngineInfo {
            name: ENGINE_NAME,
            version: ENGINE_VERSION,
            language: "jinja-compatible",
        },
        source_kinds: ["inline", "bundle"],
        context_media_type: "application/json",
        response_media_types: ["application/json", "text/plain"],
        features: FeatureInfo {
            variables: true,
            expressions: true,
            conditions: true,
            loops: true,
            filters: true,
            tests: true,
            includes: true,
            inheritance: true,
            macros: true,
            strict_undefined: true,
        },
        limits: LimitInfo {
            max_body_bytes: state.limits.max_body_bytes,
            max_context_bytes: state.limits.max_context_bytes,
            max_template_bytes: state.limits.max_template_bytes,
            max_bundle_templates: state.limits.max_bundle_templates,
            max_output_bytes: state.limits.max_output_bytes,
            fuel: state.limits.fuel,
            recursion_limit: state.limits.recursion_limit,
            timeout_ms: state.limits.timeout_ms,
        },
    })
}

#[utoipa::path(
    post,
    path = "/v1/render",
    request_body = RenderRequest,
    responses(
        (status = 200, description = "Rendered text", content(
            (RenderResponse = "application/json"),
            (String = "text/plain")
        )),
        (status = 400, description = "Invalid request or template", body = ProblemDetails, content_type = "application/problem+json"),
        (status = 406, description = "Unsupported Accept header", body = ProblemDetails, content_type = "application/problem+json"),
        (status = 413, description = "Request or template input is too large", body = ProblemDetails, content_type = "application/problem+json"),
        (status = 415, description = "Request body is not JSON", body = ProblemDetails, content_type = "application/problem+json"),
        (status = 422, description = "Execution or output limit exceeded", body = ProblemDetails, content_type = "application/problem+json"),
        (status = 500, description = "Internal wrapper error", body = ProblemDetails, content_type = "application/problem+json")
    )
)]
pub async fn render_template(
    State(state): State<AppState>,
    headers: HeaderMap,
    payload: Result<Json<RenderRequest>, axum::extract::rejection::JsonRejection>,
) -> Result<Response, ServiceError> {
    let wants_text = negotiate_response(&headers)?;
    let Json(request) = payload.map_err(map_json_rejection)?;
    let limits = (*state.limits).clone();
    let timeout = Duration::from_millis(limits.timeout_ms);
    let task = tokio::task::spawn_blocking(move || renderer::render(&request, &limits));
    let rendered = tokio::time::timeout(timeout, task)
        .await
        .map_err(|_| ServiceError::resource_limit("template rendering timed out"))?
        .map_err(|_| ServiceError::internal("renderer task failed"))??;

    if wants_text {
        let mut response = Response::new(Body::from(rendered.output));
        response.headers_mut().insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("text/plain; charset=utf-8"),
        );
        Ok(response)
    } else {
        Ok(Json(rendered).into_response())
    }
}

pub async fn openapi_document() -> Json<utoipa::openapi::OpenApi> {
    Json(ApiDoc::openapi())
}

fn negotiate_response(headers: &HeaderMap) -> Result<bool, ServiceError> {
    let Some(value) = headers.get(header::ACCEPT) else {
        return Ok(false);
    };
    let value = value
        .to_str()
        .map_err(|_| ServiceError::not_acceptable("Accept header is not valid ASCII"))?;
    if value
        .split(',')
        .map(|item| item.split(';').next().unwrap_or("").trim())
        .any(|media_type| media_type == "text/plain")
    {
        return Ok(true);
    }
    if value.split(',').any(|item| {
        matches!(
            item.split(';').next().unwrap_or("").trim(),
            "application/json" | "*/*" | "application/*"
        )
    }) {
        return Ok(false);
    }
    Err(ServiceError::not_acceptable(
        "supported response media types are application/json and text/plain",
    ))
}

fn map_json_rejection(rejection: axum::extract::rejection::JsonRejection) -> ServiceError {
    let status = rejection.status();
    let detail = rejection.body_text();
    if status == StatusCode::PAYLOAD_TOO_LARGE {
        ServiceError::payload_too_large(detail)
    } else if status == StatusCode::UNSUPPORTED_MEDIA_TYPE {
        ServiceError::new(
            "unsupported-media-type",
            StatusCode::UNSUPPORTED_MEDIA_TYPE,
            "Unsupported media type",
            detail,
        )
    } else {
        ServiceError::invalid(detail)
    }
}
