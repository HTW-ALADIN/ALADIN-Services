use axum::{
    body::{to_bytes, Body},
    http::{header, Request, StatusCode},
};
use serde_json::{json, Value};
use text_template_service::{openapi::ApiDoc, router, AppState, Limits};
use tower::ServiceExt;
use utoipa::OpenApi;

fn app() -> axum::Router {
    router(AppState::new(Limits::default()))
}

#[tokio::test]
async fn renders_json_over_http() {
    let response = app()
        .oneshot(
            Request::post("/v1/render")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "source": {"kind": "inline", "template": "Hello {{ name }}"},
                        "context": {"name": "World"}
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 1024 * 1024).await.unwrap())
            .unwrap();
    assert_eq!(body["output"], "Hello World");
}

#[tokio::test]
async fn negotiates_plain_text() {
    let response = app()
        .oneshot(
            Request::post("/v1/render")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::ACCEPT, "text/plain")
                .body(Body::from(
                    json!({
                        "source": {"kind": "inline", "template": "{{ value }}"},
                        "context": {"value": "plain"}
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        &to_bytes(response.into_body(), 1024).await.unwrap()[..],
        b"plain"
    );
}

#[tokio::test]
async fn returns_problem_details_for_invalid_json() {
    let response = app()
        .oneshot(
            Request::post("/v1/render")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from("{"))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    assert_eq!(
        response.headers()[header::CONTENT_TYPE],
        "application/problem+json"
    );
}

#[tokio::test]
async fn rejects_unknown_source_fields() {
    let response = app()
        .oneshot(
            Request::post("/v1/render")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "source": {
                            "kind": "inline",
                            "template": "Hello",
                            "unexpected": true
                        },
                        "context": {}
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    assert_eq!(
        response.headers()[header::CONTENT_TYPE],
        "application/problem+json"
    );
}

#[tokio::test]
async fn translates_template_syntax_errors() {
    let response = app()
        .oneshot(
            Request::post("/v1/render")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "source": {"kind": "inline", "template": "{% if %}"},
                        "context": {}
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 1024 * 1024).await.unwrap())
            .unwrap();
    assert_eq!(body["type"], "urn:problem:text-template:syntax-error");
}

#[tokio::test]
async fn enforces_the_http_body_limit() {
    let limits = Limits {
        max_body_bytes: 64,
        ..Limits::default()
    };
    let response = router(AppState::new(limits))
        .oneshot(
            Request::post("/v1/render")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(
                    json!({
                        "source": {"kind": "inline", "template": "This body is deliberately longer than sixty-four bytes"},
                        "context": {}
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
    assert_eq!(
        response.headers()[header::CONTENT_TYPE],
        "application/problem+json"
    );
}

#[tokio::test]
async fn exposes_health_capabilities_and_openapi() {
    for path in ["/healthz", "/v1/capabilities", "/api-docs/openapi.json"] {
        let response = app()
            .oneshot(Request::get(path).body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK, "failed path: {path}");
    }
}

#[tokio::test]
async fn capabilities_expose_configurable_limits() {
    let response = app()
        .oneshot(
            Request::get("/v1/capabilities")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 1024 * 1024).await.unwrap())
            .unwrap();

    assert_eq!(body["limits"]["maxTemplateNameBytes"], 255);
    assert_eq!(body["limits"]["maxConcurrentRenders"], 4);
}

#[tokio::test]
async fn rejects_rendering_when_capacity_is_exhausted() {
    let response = router(AppState::new(Limits {
        max_concurrent_renders: 0,
        ..Limits::default()
    }))
    .oneshot(
        Request::post("/v1/render")
            .header(header::CONTENT_TYPE, "application/json")
            .body(Body::from(
                json!({
                    "source": {"kind": "inline", "template": "ok"},
                    "context": {}
                })
                .to_string(),
            ))
            .unwrap(),
    )
    .await
    .unwrap();

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
    let body: Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 1024).await.unwrap()).unwrap();
    assert_eq!(
        body["type"],
        "urn:problem:text-template:render-capacity-exhausted"
    );
}

#[tokio::test]
async fn rejects_unsupported_response_media_types() {
    let response = app()
        .oneshot(
            Request::post("/v1/render")
                .header(header::CONTENT_TYPE, "application/json")
                .header(header::ACCEPT, "application/xml")
                .body(Body::from(
                    json!({
                        "source": {"kind": "inline", "template": "ok"},
                        "context": {}
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NOT_ACCEPTABLE);
}

#[tokio::test]
async fn negotiates_json_and_application_wildcards() {
    for accept in ["application/json", "application/*", "*/*"] {
        let response = app()
            .oneshot(
                Request::post("/v1/render")
                    .header(header::CONTENT_TYPE, "application/json")
                    .header(header::ACCEPT, accept)
                    .body(Body::from(
                        json!({
                            "source": {"kind": "inline", "template": "ok"},
                            "context": {}
                        })
                        .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK, "failed Accept: {accept}");
        assert_eq!(response.headers()[header::CONTENT_TYPE], "application/json");
    }
}

#[tokio::test]
async fn rejects_missing_json_content_type() {
    let response = app()
        .oneshot(
            Request::post("/v1/render")
                .body(Body::from(
                    json!({
                        "source": {"kind": "inline", "template": "ok"},
                        "context": {}
                    })
                    .to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNSUPPORTED_MEDIA_TYPE);
    assert_eq!(
        response.headers()[header::CONTENT_TYPE],
        "application/problem+json"
    );
}

#[test]
fn generated_openapi_describes_the_public_routes() {
    let document = serde_json::to_value(ApiDoc::openapi()).unwrap();

    assert_eq!(document["openapi"], "3.1.0");
    for path in ["/healthz", "/v1/capabilities", "/v1/render"] {
        assert!(
            document["paths"].get(path).is_some(),
            "missing path: {path}"
        );
    }

    assert!(document["components"]["schemas"]["LimitInfo"]["properties"]
        .get("maxTemplateNameBytes")
        .is_some());
    assert!(document["components"]["schemas"]["LimitInfo"]["properties"]
        .get("maxConcurrentRenders")
        .is_some());
    assert_eq!(
        document["components"]["schemas"]["TemplateSource"]["discriminator"]["propertyName"],
        "kind"
    );
    for variant in document["components"]["schemas"]["TemplateSource"]["oneOf"]
        .as_array()
        .unwrap()
    {
        assert_eq!(variant["additionalProperties"], false);
    }
    let bundle = document["components"]["schemas"]["TemplateSource"]["oneOf"]
        .as_array()
        .unwrap()
        .iter()
        .find(|variant| variant["properties"].get("templates").is_some())
        .unwrap();
    assert_eq!(bundle["properties"]["templates"]["minProperties"], 1);
}
