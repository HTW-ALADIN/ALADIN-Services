use axum::{
    routing::{get, post},
    response::IntoResponse,
    Json, Router,
};
use noise_generation_service::{
    generate_noise, list_algorithms, ApiDoc,
};
use serde_json::json;
use utoipa::OpenApi;

/// Builds the app router (mirrors main.rs).
fn build_app() -> Router {
    Router::new()
        .route("/v1/algorithms", get(list_algorithms))
        .route("/v1/noise", post(generate_noise))
        .route(
            "/api-docs/openapi.json",
            get(|| async { Json(ApiDoc::openapi()).into_response() }),
        )
}

/// Starts the server on a random available port and returns the base URL.
async fn start_test_server() -> String {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .unwrap();
    let port = listener.local_addr().unwrap().port();
    let app = build_app();

    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    // Give the server a moment to start
    tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    format!("http://127.0.0.1:{}", port)
}

// ─── Helper: POST /v1/noise and check status 201 ─────────────────────────────

async fn post_noise(
    url: &str,
    algorithm: &str,
    params: serde_json::Value,
    size: Vec<usize>,
) -> serde_json::Value {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/v1/noise", url))
        .json(&json!({
            "algorithm": algorithm,
            "params": params,
            "sampling": { "mode": "grid", "size": size },
            "output": { "format": "json", "normalize": false }
        }))
        .send()
        .await
        .unwrap();

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        panic!("POST /v1/noise {} failed with {}: {}", algorithm, status, body);
    }

    response.json().await.unwrap()
}

// ─── Tests: GET /v1/algorithms ───────────────────────────────────────────────

#[tokio::test]
async fn test_list_algorithms_returns_15() {
    let url = start_test_server().await;
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/v1/algorithms", url))
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), 200);
    let algos: Vec<serde_json::Value> = response.json().await.unwrap();
    assert_eq!(algos.len(), 15);
}

#[tokio::test]
async fn test_list_algorithms_structure() {
    let url = start_test_server().await;
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/v1/algorithms", url))
        .send()
        .await
        .unwrap();
    let algos: Vec<serde_json::Value> = response.json().await.unwrap();
    let first = &algos[0];
    assert_eq!(first["name"], "perlin");
    assert!(first["defaults"].is_object());
    assert!(first["defaults"]["seed"].is_null());
}

#[tokio::test]
async fn test_list_algorithms_fbm_defaults() {
    let url = start_test_server().await;
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/v1/algorithms", url))
        .send()
        .await
        .unwrap();
    let algos: Vec<serde_json::Value> = response.json().await.unwrap();
    let fbm = algos.iter().find(|a| a["name"] == "fbm").unwrap();
    assert_eq!(fbm["defaults"]["octaves"], 4);
    assert_eq!(fbm["defaults"]["frequency"], 0.1);
    assert_eq!(fbm["defaults"]["lacunarity"], 2.0);
    assert_eq!(fbm["defaults"]["persistence"], 0.5);
}

// ─── Tests: POST /v1/noise — seed consistency (THE CRITICAL FIX) ─────────────

#[tokio::test]
async fn test_params_used_with_explicit_seed() {
    let url = start_test_server().await;
    let result = post_noise(&url, "perlin", json!({"seed": 42}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["seed"], 42);
}

#[tokio::test]
async fn test_params_used_without_seed_has_concrete_value() {
    let url = start_test_server().await;
    let result = post_noise(&url, "perlin", json!({}), vec![4, 4]).await;
    let seed = result["params_used"]["seed"].as_u64().unwrap();
    assert!(seed > 0, "auto-generated seed must be non-zero, got {}", seed);
}

#[tokio::test]
async fn test_params_used_seed_matches_generation() {
    // POST twice with same empty params → different random seeds expected
    let url = start_test_server().await;
    let r1 = post_noise(&url, "perlin", json!({}), vec![4, 4]).await;
    let r2 = post_noise(&url, "perlin", json!({}), vec![4, 4]).await;
    let s1 = r1["params_used"]["seed"].as_u64().unwrap();
    let s2 = r2["params_used"]["seed"].as_u64().unwrap();
    // Different requests → different random seeds (statistically certain)
    assert_ne!(
        s1, s2,
        "two requests without seed should produce different random seeds"
    );
    // The data should differ because seeds differ → consistency check
    assert_ne!(r1["data"], r2["data"], "different seeds must produce different data");
}

#[tokio::test]
async fn test_params_used_reproducibility() {
    // Same explicit seed → identical data AND identical params_used
    let url = start_test_server().await;
    let r1 = post_noise(&url, "perlin", json!({"seed": 123}), vec![4, 4]).await;
    let r2 = post_noise(&url, "perlin", json!({"seed": 123}), vec![4, 4]).await;
    assert_eq!(r1["data"], r2["data"], "same seed must produce same data");
    assert_eq!(r1["params_used"], r2["params_used"]);
}

// ─── Tests: POST /v1/noise — params_used per algorithm family ────────────────

#[tokio::test]
async fn test_params_used_cellular_explicit() {
    let url = start_test_server().await;
    let result = post_noise(
        &url,
        "cellular",
        json!({"seed": 7, "distance_function": "manhattan", "return_type": "distance", "jitter": 0.9}),
        vec![4, 4],
    )
    .await;
    assert_eq!(result["params_used"]["seed"], 7);
    assert_eq!(result["params_used"]["distance_function"], "manhattan");
    assert_eq!(result["params_used"]["return_type"], "distance");
    assert!((result["params_used"]["jitter"].as_f64().unwrap() - 0.9).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_cellular_defaults() {
    let url = start_test_server().await;
    let result = post_noise(&url, "cellular", json!({}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["distance_function"], "euclidean");
    assert_eq!(result["params_used"]["return_type"], "cell_value");
    assert!((result["params_used"]["jitter"].as_f64().unwrap() - 0.45).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_fbm_explicit() {
    let url = start_test_server().await;
    let result = post_noise(
        &url,
        "fbm",
        json!({"seed": 1, "octaves": 6, "frequency": 0.05, "lacunarity": 3.0, "persistence": 0.3}),
        vec![4, 4],
    )
    .await;
    assert_eq!(result["params_used"]["seed"], 1);
    assert_eq!(result["params_used"]["octaves"], 6);
    assert!((result["params_used"]["frequency"].as_f64().unwrap() - 0.05).abs() < 1e-6);
    assert!((result["params_used"]["lacunarity"].as_f64().unwrap() - 3.0).abs() < 1e-6);
    assert!((result["params_used"]["persistence"].as_f64().unwrap() - 0.3).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_fbm_defaults() {
    let url = start_test_server().await;
    let result = post_noise(&url, "fbm", json!({}), vec![4, 4]).await;
    assert!(result["params_used"]["seed"].as_u64().unwrap() > 0);
    assert_eq!(result["params_used"]["octaves"], 4);
    assert!((result["params_used"]["frequency"].as_f64().unwrap() - 0.1).abs() < 1e-6);
    assert!((result["params_used"]["lacunarity"].as_f64().unwrap() - 2.0).abs() < 1e-6);
    assert!((result["params_used"]["persistence"].as_f64().unwrap() - 0.5).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_pingpong() {
    let url = start_test_server().await;
    let result = post_noise(&url, "pingpong", json!({"seed": 42, "strength": 3.0}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["seed"], 42);
    assert!((result["params_used"]["strength"].as_f64().unwrap() - 3.0).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_domain_warp() {
    let url = start_test_server().await;
    let result = post_noise(
        &url,
        "domain_warp",
        json!({"seed": 99, "amplitude": 30.0}),
        vec![4, 4],
    )
    .await;
    assert_eq!(result["params_used"]["seed"], 99);
    assert!((result["params_used"]["amplitude"].as_f64().unwrap() - 30.0).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_combinator_add() {
    let url = start_test_server().await;
    let result = post_noise(
        &url,
        "combinator",
        json!({"seed": 10, "op": "add", "blend_factor": 0.3}),
        vec![4, 4],
    )
    .await;
    assert_eq!(result["params_used"]["seed"], 10);
    assert_eq!(result["params_used"]["op"], "add");
    assert!((result["params_used"]["blend_factor"].as_f64().unwrap() - 0.3).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_combinator_defaults() {
    let url = start_test_server().await;
    let result = post_noise(&url, "combinator", json!({}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["op"], "add");
    assert!((result["params_used"]["blend_factor"].as_f64().unwrap() - 0.5).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_utility_constant() {
    let url = start_test_server().await;
    let result = post_noise(
        &url,
        "utility",
        json!({"kind": "constant", "value": 0.75}),
        vec![4, 4],
    )
    .await;
    assert_eq!(result["params_used"]["kind"], "constant");
    assert!((result["params_used"]["value"].as_f64().unwrap() - 0.75).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_utility_cylinders() {
    let url = start_test_server().await;
    let result = post_noise(&url, "utility", json!({"kind": "cylinders"}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["kind"], "cylinders");
}

#[tokio::test]
async fn test_params_used_billow_defaults() {
    let url = start_test_server().await;
    let result = post_noise(&url, "billow", json!({"seed": 1}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["seed"], 1);
    assert_eq!(result["params_used"]["octaves"], 4);
    assert!((result["params_used"]["persistence"].as_f64().unwrap() - 0.5).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_ridged_multi_defaults() {
    let url = start_test_server().await;
    let result = post_noise(&url, "ridged_multi", json!({"seed": 1}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["seed"], 1);
    assert!((result["params_used"]["persistence"].as_f64().unwrap() - 0.5).abs() < 1e-6);
}

#[tokio::test]
async fn test_params_used_hybrid_multi_defaults() {
    let url = start_test_server().await;
    let result = post_noise(&url, "hybrid_multi", json!({"seed": 1}), vec![4, 4]).await;
    assert_eq!(result["params_used"]["seed"], 1);
    assert!((result["params_used"]["persistence"].as_f64().unwrap() - 0.25).abs() < 1e-6);
}

// ─── Tests: Response structure ────────────────────────────────────────────────

#[tokio::test]
async fn test_response_structure() {
    let url = start_test_server().await;
    let result = post_noise(&url, "simplex", json!({"seed": 42}), vec![5, 5]).await;
    assert!(result["id"].as_str().unwrap().starts_with("nsf_"));
    assert_eq!(result["status"], "completed");
    assert_eq!(result["algorithm"], "simplex");
    assert_eq!(result["size"], json!([5, 5]));
    assert!(result["params_used"].is_object());
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 5);
    assert_eq!(data[0].as_array().unwrap().len(), 5);
}

#[tokio::test]
async fn test_response_contains_params_used() {
    let url = start_test_server().await;
    let result = post_noise(&url, "perlin", json!({"seed": 42}), vec![4, 4]).await;
    assert!(
        result.get("params_used").is_some(),
        "response must contain params_used"
    );
}

// ─── Tests: Error cases ──────────────────────────────────────────────────────

#[tokio::test]
async fn test_error_unsupported_dimension() {
    let url = start_test_server().await;
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/v1/noise", url))
        .json(&json!({
            "algorithm": "perlin",
            "params": {},
            "sampling": { "mode": "grid", "size": [10] },
            "output": { "format": "json", "normalize": false }
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), 400);
    let result: serde_json::Value = response.json().await.unwrap();
    assert!(result["status"].as_str().unwrap().starts_with("error:"));
    assert_eq!(result["algorithm"], "perlin");
    assert_eq!(result["data"], serde_json::Value::Null);
    assert_eq!(result["params_used"], serde_json::Value::Null);
}

// ─── Tests: Param differences produce different output ───────────────────────

#[tokio::test]
async fn test_cellular_parameters_affect_output() {
    let url = start_test_server().await;

    let r1 = post_noise(
        &url,
        "cellular",
        json!({"distance_function": "euclidean", "return_type": "cell_value", "jitter": 0.45}),
        vec![5, 5],
    )
    .await;
    let r2 = post_noise(
        &url,
        "cellular",
        json!({"distance_function": "manhattan", "return_type": "distance", "jitter": 0.9}),
        vec![5, 5],
    )
    .await;

    assert_ne!(r1["data"], r2["data"]);
    assert_ne!(r1["params_used"], r2["params_used"]);
}

#[tokio::test]
async fn test_fbm_seed_affects_output() {
    let url = start_test_server().await;
    let r1 = post_noise(&url, "fbm", json!({"seed": 1, "octaves": 3}), vec![20, 20]).await;
    let r2 = post_noise(&url, "fbm", json!({"seed": 2, "octaves": 4}), vec![20, 20]).await;
    assert_ne!(r1["data"], r2["data"]);
}

#[tokio::test]
async fn test_white_noise_seed_affects_output() {
    let url = start_test_server().await;
    let r1 = post_noise(&url, "white", json!({"seed": 1}), vec![20, 20]).await;
    let r2 = post_noise(&url, "white", json!({"seed": 2}), vec![20, 20]).await;
    assert_ne!(r1["data"], r2["data"]);
}

// ─── Tests: Edge cases (empty params, normalize) ─────────────────────────────

#[tokio::test]
async fn test_empty_params_still_returns_params_used() {
    let url = start_test_server().await;
    let result = post_noise(&url, "value", json!({}), vec![4, 4]).await;
    assert!(result["params_used"]["seed"].as_u64().unwrap() > 0);
}

// ─── Tests: Dimension support ────────────────────────────────────────────────

/// Helper: POST /v1/noise and return raw reqwest::Response (for error checking).
async fn post_noise_raw(
    url: &str,
    algorithm: &str,
    params: serde_json::Value,
    size: Vec<usize>,
) -> reqwest::Response {
    let client = reqwest::Client::new();
    client
        .post(format!("{}/v1/noise", url))
        .json(&json!({
            "algorithm": algorithm,
            "params": params,
            "sampling": { "mode": "grid", "size": size },
            "output": { "format": "json", "normalize": false }
        }))
        .send()
        .await
        .unwrap()
}

/// Returns the algorithms that should support a given number of dimensions.
/// 1 = 1D, 2 = 2D, 3 = 3D.
fn algorithms_for_dim(dim: usize) -> Vec<&'static str> {
    match dim {
        1 => vec!["white"],
        2 | 3 => vec![
            "perlin", "simplex", "opensimplex2", "supersimplex",
            "value", "cellular", "fbm", "billow", "ridged_multi",
            "hybrid_multi", "pingpong", "domain_warp", "combinator",
            "utility", "white",
        ],
        _ => algorithms_for_4d(),
    }
}

#[tokio::test]
async fn test_all_algorithms_2d_success() {
    let url = start_test_server().await;
    for alg in algorithms_for_dim(2) {
        let params = if alg == "utility" {
            json!({"kind": "constant", "value": 0.5})
        } else {
            json!({"seed": 42})
        };
        let result = post_noise(&url, alg, params, vec![4, 4]).await;
        assert_eq!(result["algorithm"], alg);
        assert_eq!(result["size"], json!([4, 4]));
        assert_eq!(result["status"], "completed");
        let data = result["data"].as_array().unwrap();
        assert_eq!(data.len(), 4, "algorithm {}: expected 4 rows", alg);
        assert_eq!(data[0].as_array().unwrap().len(), 4, "algorithm {}: expected 4 cols", alg);
        assert!(result["params_used"].is_object());
    }
}

#[tokio::test]
async fn test_all_algorithms_3d_success() {
    let url = start_test_server().await;
    for alg in algorithms_for_dim(3) {
        let params = if alg == "utility" {
            json!({"kind": "constant", "value": 0.5})
        } else {
            json!({"seed": 42})
        };
        let result = post_noise(&url, alg, params, vec![3, 3, 3]).await;
        assert_eq!(result["algorithm"], alg);
        assert_eq!(result["size"], json!([3, 3, 3]));
        assert_eq!(result["status"], "completed");
        let volume = result["data"].as_array().unwrap();
        assert_eq!(volume.len(), 3, "algorithm {}: expected depth 3", alg);
        assert_eq!(volume[0].as_array().unwrap().len(), 3, "algorithm {}: expected 3 rows", alg);
        assert_eq!(
            volume[0].as_array().unwrap()[0].as_array().unwrap().len(),
            3,
            "algorithm {}: expected 3 cols",
            alg
        );
    }
}

#[tokio::test]
async fn test_white_noise_1d_success() {
    let url = start_test_server().await;
    let result = post_noise(&url, "white", json!({"seed": 1}), vec![10]).await;
    assert_eq!(result["size"], json!([10]));
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 10);
    assert_eq!(result["algorithm"], "white");
    assert_eq!(result["params_used"]["seed"], 1);
}

#[tokio::test]
async fn test_non_white_1d_fails_with_400() {
    let url = start_test_server().await;
    for alg in algorithms_for_dim(2) {
        if alg == "white" {
            continue;
        }
        let response = post_noise_raw(&url, alg, json!({"seed": 42}), vec![10]).await;
        assert_eq!(
            response.status(),
            400,
            "algorithm {} should fail with 400 for 1D",
            alg
        );
        let result: serde_json::Value = response.json().await.unwrap();
        assert!(
            result["status"].as_str().unwrap().starts_with("error:"),
            "algorithm {}: expected error status, got {:?}",
            alg,
            result["status"]
        );
        assert_eq!(result["params_used"], serde_json::Value::Null);
        assert_eq!(result["data"], serde_json::Value::Null);
        assert_eq!(result["algorithm"], alg);
    }
}

#[tokio::test]
async fn test_dimension_inferred_from_size_length() {
    let url = start_test_server().await;

    // 1D with white noise
    let r1 = post_noise(&url, "white", json!({"seed": 1}), vec![5]).await;
    assert_eq!(r1["size"], json!([5]));

    // 2D with white noise
    let r2 = post_noise(&url, "white", json!({"seed": 1}), vec![5, 6]).await;
    assert_eq!(r2["size"], json!([5, 6]));
    assert_eq!(r2["data"].as_array().unwrap().len(), 6);
    assert_eq!(r2["data"].as_array().unwrap()[0].as_array().unwrap().len(), 5);

    // 3D with white noise
    let r3 = post_noise(&url, "white", json!({"seed": 1}), vec![5, 6, 7]).await;
    assert_eq!(r3["size"], json!([5, 6, 7]));
    assert_eq!(r3["data"].as_array().unwrap().len(), 7);
    assert_eq!(r3["data"].as_array().unwrap()[0].as_array().unwrap().len(), 6);
    assert_eq!(
        r3["data"].as_array().unwrap()[0].as_array().unwrap()[0]
            .as_array()
            .unwrap()
            .len(),
        5
    );
}

#[tokio::test]
async fn test_1d_error_message_contains_algorithm_name() {
    let url = start_test_server().await;
    let response = post_noise_raw(&url, "fbm", json!({"seed": 42}), vec![10]).await;
    assert_eq!(response.status(), 400);
    let result: serde_json::Value = response.json().await.unwrap();
    let msg = result["status"].as_str().unwrap();
    assert!(msg.contains("fbm"), "error should mention algorithm name");
}

#[tokio::test]
async fn test_perlin_2d_and_3d_different_data() {
    let url = start_test_server().await;
    let r2d = post_noise(&url, "perlin", json!({"seed": 42}), vec![4, 4]).await;
    let r3d = post_noise(&url, "perlin", json!({"seed": 42}), vec![4, 4, 4]).await;
    assert!(r2d["data"].as_array().unwrap()[0].as_array().is_some());
    assert!(r3d["data"].as_array().unwrap()[0]
        .as_array()
        .unwrap()[0]
        .as_array()
        .is_some());
    assert_eq!(r2d["params_used"], r3d["params_used"]);
}

#[tokio::test]
async fn test_all_2d_algorithms_produce_rectangular_grid() {
    let url = start_test_server().await;
    for alg in algorithms_for_dim(2) {
        if alg == "white" || alg == "utility" {
            continue;
        }
        let result = post_noise(&url, alg, json!({"seed": 42}), vec![3, 5]).await;
        assert_eq!(result["size"], json!([3, 5]));
        let data = result["data"].as_array().unwrap();
        assert_eq!(data.len(), 5, "{}: expected 5 rows (height)", alg);
        assert_eq!(
            data[0].as_array().unwrap().len(),
            3,
            "{}: expected 3 cols (width)",
            alg
        );
    }
}

#[tokio::test]
async fn test_normalize_output() {
    let url = start_test_server().await;
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/v1/noise", url))
        .json(&json!({
            "algorithm": "perlin",
            "params": {"seed": 42},
            "sampling": {"mode": "grid", "size": [4, 4]},
            "output": {"format": "json", "normalize": true}
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), 201);
    let result: serde_json::Value = response.json().await.unwrap();
    assert!(result["params_used"].is_object());
    // Data should be in [0, 1] after normalization
    for row in result["data"].as_array().unwrap() {
        for val in row.as_array().unwrap() {
            let v = val.as_f64().unwrap();
            assert!((0.0..=1.0).contains(&v), "normalized value {} out of range", v);
        }
    }
}

// ─── Helper: algorithms that SUPPORT 4D ─────────────────────────────────

fn algorithms_for_4d() -> Vec<&'static str> {
    vec![
        "simplex", "fbm", "billow", "ridged_multi", "hybrid_multi",
        "combinator", "utility", "white",
    ]
}

/// Algorithms that do NOT support 4D (FNL-only, DomainWarp, SuperSimplex).
fn algorithms_not_for_4d() -> Vec<&'static str> {
    vec![
        "perlin", "opensimplex2", "supersimplex", "value", "cellular",
        "pingpong", "domain_warp",
    ]
}

// ─── Tests: 4D support ─────────────────────────────────────────────────

#[tokio::test]
async fn test_4d_success_for_noise_rs_algorithms() {
    let url = start_test_server().await;
    for alg in algorithms_for_4d() {
        let params = if alg == "utility" {
            json!({"kind": "constant", "value": 0.5})
        } else {
            json!({"seed": 42})
        };
        let result = post_noise(&url, alg, params, vec![3, 3, 3, 3]).await;
        assert_eq!(
            result["status"], "completed",
            "algorithm {} should succeed with 4D",
            alg
        );
        assert_eq!(result["size"], json!([3, 3, 3, 3]));
        let hypervolume = result["data"].as_array().unwrap();
        assert_eq!(hypervolume.len(), 3, "{}: expected 4th dim size 3", alg);
        assert_eq!(
            hypervolume[0].as_array().unwrap().len(),
            3,
            "{}: expected depth 3",
            alg
        );
        assert_eq!(
            hypervolume[0].as_array().unwrap()[0].as_array().unwrap().len(),
            3,
            "{}: expected 3 rows",
            alg
        );
        assert_eq!(
            hypervolume[0].as_array().unwrap()[0].as_array().unwrap()[0]
                .as_array()
                .unwrap()
                .len(),
            3,
            "{}: expected 3 cols",
            alg
        );
        assert!(result["params_used"].is_object());
    }
}

#[tokio::test]
async fn test_4d_rejected_for_fnl_algorithms() {
    let url = start_test_server().await;
    for alg in algorithms_not_for_4d() {
        let params = if alg == "utility" {
            json!({"kind": "constant", "value": 0.5})
        } else {
            json!({"seed": 42})
        };
        let response = post_noise_raw(&url, alg, params, vec![4, 4, 4, 4]).await;
        assert_eq!(
            response.status(),
            400,
            "algorithm {} should reject 4D with 400",
            alg
        );
        let result: serde_json::Value = response.json().await.unwrap();
        let msg = result["status"].as_str().unwrap();
        assert!(
            msg.contains("4D") || msg.contains("dimension") || msg.contains("support"),
            "algorithm {}: error should mention 4D/dimension, got: {}",
            alg,
            msg
        );
    }
}

#[tokio::test]
async fn test_5d_rejected_for_white_noise() {
    let url = start_test_server().await;
    let response = post_noise_raw(&url, "white", json!({"seed": 42}), vec![4, 4, 4, 4, 4]).await;
    assert_eq!(response.status(), 400);
    let result: serde_json::Value = response.json().await.unwrap();
    let msg = result["status"].as_str().unwrap();
    assert!(
        msg.contains("5D") || msg.contains("dimension") || msg.contains("support"),
        "error should mention dimension limit (5D)"
    );
}
