use std::{sync::Arc, time::Duration};

use axum::{
    body::Body,
    extract::{DefaultBodyLimit, State},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use tokio::sync::Semaphore;
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
    renderer::{self, TemplateCache, ENGINE_NAME, ENGINE_VERSION},
};

#[derive(Clone)]
pub struct AppState {
    pub limits: Arc<Limits>,
    render_slots: Arc<Semaphore>,
    template_cache: TemplateCache,
}

impl AppState {
    pub fn new(limits: Limits) -> Self {
        let render_slots = Arc::new(Semaphore::new(limits.max_concurrent_renders));
        Self {
            limits: Arc::new(limits),
            render_slots,
            template_cache: TemplateCache::new(),
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
            max_template_name_bytes: state.limits.max_template_name_bytes,
            max_concurrent_renders: state.limits.max_concurrent_renders,
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
        (status = 503, description = "All render workers are busy", body = ProblemDetails, content_type = "application/problem+json"),
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
    let permit = state
        .render_slots
        .clone()
        .try_acquire_owned()
        .map_err(|_| ServiceError::unavailable("all render workers are busy"))?;
    let limits = (*state.limits).clone();
    let timeout = Duration::from_millis(limits.timeout_ms);
    let cache = state.template_cache.clone();
    let task = tokio::task::spawn_blocking(move || {
        let _permit = permit;
        renderer::render_cached(&request, &limits, &cache)
    });
    let rendered = await_render_task(task, timeout).await?;

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

async fn await_render_task(
    task: tokio::task::JoinHandle<Result<RenderResponse, ServiceError>>,
    timeout: Duration,
) -> Result<RenderResponse, ServiceError> {
    tokio::time::timeout(timeout, task)
        .await
        .map_err(|_| ServiceError::resource_limit("template rendering timed out"))?
        .map_err(|_| ServiceError::internal("renderer task failed"))?
}

pub async fn openapi_document() -> Json<utoipa::openapi::OpenApi> {
    Json(ApiDoc::openapi())
}

fn negotiate_response(headers: &HeaderMap) -> Result<bool, ServiceError> {
    if !headers.contains_key(header::ACCEPT) {
        return Ok(false);
    }

    let mut json = None;
    let mut text = None;
    for value in headers.get_all(header::ACCEPT) {
        let value = value
            .to_str()
            .map_err(|_| ServiceError::not_acceptable("Accept header is not valid ASCII"))?;
        for item in value.split(',') {
            let (media_type, quality) = parse_media_range(item)?;
            update_preference(&mut json, media_type, quality, "application/json");
            update_preference(&mut text, media_type, quality, "text/plain");
        }
    }

    let json_quality = json.map_or(0, |(_, quality)| quality);
    let text_quality = text.map_or(0, |(_, quality)| quality);
    if json_quality == 0 && text_quality == 0 {
        Err(ServiceError::not_acceptable(
            "supported response media types are application/json and text/plain",
        ))
    } else {
        Ok(text_quality > json_quality)
    }
}

fn parse_media_range(item: &str) -> Result<(&str, u16), ServiceError> {
    let mut parts = item.split(';');
    let media_type = parts.next().unwrap_or("").trim();
    let mut quality = 1000;
    let mut quality_seen = false;
    for parameter in parts {
        let Some((name, value)) = parameter.trim().split_once('=') else {
            continue;
        };
        if name.trim().eq_ignore_ascii_case("q") {
            if quality_seen {
                return Err(invalid_accept_quality());
            }
            quality = parse_quality(value.trim()).ok_or_else(invalid_accept_quality)?;
            quality_seen = true;
        }
    }
    Ok((media_type, quality))
}

fn parse_quality(value: &str) -> Option<u16> {
    let (whole, fraction) = value.split_once('.').unwrap_or((value, ""));
    if fraction.len() > 3 || !fraction.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }
    let fraction = format!("{fraction:0<3}").parse::<u16>().ok()?;
    match whole {
        "" | "0" => Some(fraction),
        "1" if fraction == 0 => Some(1000),
        _ => None,
    }
}

fn update_preference(
    preference: &mut Option<(u8, u16)>,
    media_range: &str,
    quality: u16,
    representation: &str,
) {
    let (range_type, range_subtype) = media_range.split_once('/').unwrap_or(("", ""));
    let (representation_type, representation_subtype) = representation.split_once('/').unwrap();
    let specificity = if range_type.eq_ignore_ascii_case(representation_type)
        && range_subtype.eq_ignore_ascii_case(representation_subtype)
    {
        2
    } else if range_type.eq_ignore_ascii_case(representation_type) && range_subtype == "*" {
        1
    } else if range_type == "*" && range_subtype == "*" {
        0
    } else {
        return;
    };
    if preference.is_none_or(|(current_specificity, current_quality)| {
        specificity > current_specificity
            || (specificity == current_specificity && quality > current_quality)
    }) {
        *preference = Some((specificity, quality));
    }
}

fn invalid_accept_quality() -> ServiceError {
    ServiceError::not_acceptable("Accept header contains an invalid q value")
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

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use axum::http::{header, HeaderMap, HeaderValue, StatusCode};

    use super::{await_render_task, negotiate_response, parse_quality, AppState};
    use crate::config::Limits;
    use crate::{error::ServiceError, model::RenderResponse};

    #[test]
    fn rejects_non_ascii_accept_headers() {
        let mut headers = HeaderMap::new();
        headers.insert(header::ACCEPT, HeaderValue::from_bytes(&[0xff]).unwrap());

        let error = negotiate_response(&headers).unwrap_err();

        assert_eq!(error.status, StatusCode::NOT_ACCEPTABLE);
    }

    #[test]
    fn negotiates_quality_values_and_specific_exclusions() {
        for (accept, wants_text) in [
            ("application/json;q=0.4, text/plain;q=0.8", true),
            ("text/plain;q=0, */*;q=1", false),
            ("TEXT/PLAIN;Q=.8, APPLICATION/JSON;Q=.4", true),
            ("text/plain;q=0.5, application/json;q=0.5", false),
            ("text/plain; charset=utf-8", true),
            ("text/plain; charset", true),
        ] {
            let mut headers = HeaderMap::new();
            headers.insert(header::ACCEPT, HeaderValue::from_str(accept).unwrap());
            assert_eq!(negotiate_response(&headers).unwrap(), wants_text);
        }
    }

    #[test]
    fn rejects_unacceptable_or_invalid_quality_values() {
        for accept in [
            "text/plain;q=0, application/json;q=0",
            "text/plain;q=1.1",
            "text/plain;q=abc",
            "text/plain;q=1;q=0",
        ] {
            let mut headers = HeaderMap::new();
            headers.insert(header::ACCEPT, HeaderValue::from_str(accept).unwrap());
            assert_eq!(
                negotiate_response(&headers).unwrap_err().status,
                StatusCode::NOT_ACCEPTABLE
            );
        }
    }

    #[test]
    fn parses_valid_quality_forms() {
        assert_eq!(parse_quality("0"), Some(0));
        assert_eq!(parse_quality("0.12"), Some(120));
        assert_eq!(parse_quality("1.000"), Some(1000));
        assert_eq!(parse_quality("0.1234"), None);
    }

    #[tokio::test]
    async fn maps_timed_out_and_panicked_renderer_tasks() {
        let state = AppState::new(Limits {
            max_concurrent_renders: 1,
            ..Limits::default()
        });
        let permit = state.render_slots.clone().try_acquire_owned().unwrap();
        let slow = tokio::task::spawn_blocking(move || {
            let _permit = permit;
            std::thread::sleep(Duration::from_millis(25));
            Err(ServiceError::invalid("unused"))
        });
        let timeout = await_render_task(slow, Duration::ZERO).await.unwrap_err();
        assert_eq!(timeout.code, "resource-limit");
        assert_eq!(state.render_slots.available_permits(), 0);
        tokio::time::sleep(Duration::from_millis(30)).await;
        assert_eq!(state.render_slots.available_permits(), 1);

        let panicked = tokio::task::spawn_blocking(|| -> Result<RenderResponse, ServiceError> {
            panic!("renderer panic for contract test")
        });
        let internal = await_render_task(panicked, Duration::from_secs(1))
            .await
            .unwrap_err();
        assert_eq!(internal.code, "internal-error");
    }
}
