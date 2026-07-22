use serde_json::json;

#[tokio::test]
async fn test_perlin_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "perlin",
            "params": {},
            "sampling": {
                "mode": "grid",
                "dimensions": 2
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);
}

#[tokio::test]
async fn test_simplex_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "simplex",
            "params": {},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    assert!(result["id"].as_str().unwrap().starts_with("nsf_"));
    assert_eq!(result["status"], "completed");
    assert_eq!(result["algorithm"], "simplex");
    assert_eq!(result["size"], json!([5, 5]));

    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 5);
    assert_eq!(data[0].as_array().unwrap().len(), 5);
}

#[tokio::test]
async fn test_opensimplex2_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "opensimplex2",
            "params": {},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 5);
    assert_eq!(data[0].as_array().unwrap().len(), 5);
}

#[tokio::test]
async fn test_supersimplex_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "supersimplex",
            "params": {},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 5);
    assert_eq!(data[0].as_array().unwrap().len(), 5);
}

#[tokio::test]
async fn test_value_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "value",
            "params": {},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 5);
    assert_eq!(data[0].as_array().unwrap().len(), 5);
}

#[tokio::test]
async fn test_cellular_parameters() {
    let client = reqwest::Client::new();

    let resp1 = client.post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "cellular",
            "params": {"distance_function": "euclidean", "return_type": "cell_value", "jitter": 0.45},
            "sampling": {"mode": "grid", "dimensions": 2, "size": [5, 5]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send().await.unwrap();
    let field1 = resp1.json::<serde_json::Value>().await.unwrap()["data"].clone();

    let resp2 = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "cellular",
            "params": {"distance_function": "manhattan", "return_type": "distance", "jitter": 0.9},
            "sampling": {"mode": "grid", "dimensions": 2, "size": [5, 5]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send()
        .await
        .unwrap();
    let field2 = resp2.json::<serde_json::Value>().await.unwrap()["data"].clone();

    assert_ne!(field1, field2);
}

#[tokio::test]
async fn test_fbm_seed_parameter() {
    let client = reqwest::Client::new();

    let params1 = json!({"seed": 1, "octaves": 3});
    let resp1 = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "fbm",
            "params": params1,
            "sampling": {"mode": "grid", "dimensions": 2, "size": [20, 20]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send()
        .await
        .unwrap();
    let field1: Vec<Vec<f64>> =
        serde_json::from_value(resp1.json::<serde_json::Value>().await.unwrap()["data"].clone())
            .unwrap();

    let params2 = json!({"seed": 2, "octaves": 4});
    let resp2 = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "fbm",
            "params": params2,
            "sampling": {"mode": "grid", "dimensions": 2, "size": [20, 20]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send()
        .await
        .unwrap();
    let field2: Vec<Vec<f64>> =
        serde_json::from_value(resp2.json::<serde_json::Value>().await.unwrap()["data"].clone())
            .unwrap();

    let mut diff = 0.0;
    for y in 0..20 {
        for x in 0..20 {
            diff += (field1[y][x] - field2[y][x]).abs();
        }
    }
    let mean_diff = diff / (20.0 * 20.0);
    assert!(
        mean_diff > 0.01,
        "Fields should be significantly different, mean_diff: {}",
        mean_diff
    );
}

#[tokio::test]
async fn test_billow_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "billow",
            "params": {"seed": 1, "octaves": 3, "persistence": 0.5},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);
}

#[tokio::test]
async fn test_ridged_multi_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "ridged_multi",
            "params": {"seed": 1, "octaves": 3, "lacunarity": 2.0, "gain": 0.5},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);
}

#[tokio::test]
async fn test_hybrid_multi_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "hybrid_multi",
            "params": {"seed": 1, "octaves": 3, "persistence": 0.5},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);
}

#[tokio::test]
async fn test_pingpong_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "pingpong",
            "params": {"seed": 1, "strength": 2.0},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);
}

#[tokio::test]
async fn test_domain_warp_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "domain_warp",
            "params": {"seed": 1, "warp_type": "open_simplex2", "amplitude": 30.0},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);
}

#[tokio::test]
async fn test_combinator_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "combinator",
            "params": {"op": "add"},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 5);
    assert_eq!(data[0].as_array().unwrap().len(), 5);
}

#[tokio::test]
async fn test_utility_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "utility",
            "params": {"kind": "constant", "value": 0.5},
            "sampling": {
                "mode": "grid",
                "dimensions": 2,
                "size": [5, 5]
            },
            "output": {
                "format": "json",
                "normalize": "none"
            }
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    let data: Vec<Vec<f64>> = serde_json::from_value(result["data"].clone()).unwrap();
    assert_eq!(data.len(), 5);
    assert_eq!(data[0].len(), 5);
    assert_eq!(data[0][0], 0.5);
}

#[tokio::test]
async fn test_white_noise_seed_parameter() {
    let client = reqwest::Client::new();

    let params1 = json!({"seed": 1});
    let resp1 = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "white",
            "params": params1,
            "sampling": {"mode": "grid", "dimensions": 2, "size": [20, 20]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send()
        .await
        .unwrap();
    let field1: Vec<Vec<f64>> =
        serde_json::from_value(resp1.json::<serde_json::Value>().await.unwrap()["data"].clone())
            .unwrap();

    let params2 = json!({"seed": 2});
    let resp2 = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "white",
            "params": params2,
            "sampling": {"mode": "grid", "dimensions": 2, "size": [20, 20]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send()
        .await
        .unwrap();
    let field2: Vec<Vec<f64>> =
        serde_json::from_value(resp2.json::<serde_json::Value>().await.unwrap()["data"].clone())
            .unwrap();

    let mut diff = 0.0;
    for y in 0..20 {
        for x in 0..20 {
            diff += (field1[y][x] - field2[y][x]).abs();
        }
    }
    let mean_diff = diff / (20.0 * 20.0);
    assert!(
        mean_diff > 0.01,
        "Fields should be significantly different, mean_diff: {}",
        mean_diff
    );
}

// ─── Performance Tests ───────────────────────────────────────────────────────

#[tokio::test]
async fn test_performance_medium_grid() {
    let client = reqwest::Client::new();
    let start = std::time::Instant::now();

    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "perlin",
            "params": {"seed": 42},
            "sampling": {
                "mode": "2d",
                "dimensions": 2,
                "size": [256, 256]
            }
        }))
        .send()
        .await
        .unwrap();

    let elapsed = start.elapsed();
    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 256);
    assert_eq!(data[0].as_array().unwrap().len(), 256);

    assert!(
        elapsed.as_secs() < 5,
        "256×256 grid generation took too long: {:?}",
        elapsed
    );

    println!("Performance test (256×256): {:?}", elapsed);
}

#[tokio::test]
async fn test_performance_large_grid() {
    let client = reqwest::Client::new();
    let start = std::time::Instant::now();

    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "perlin",
            "params": {"seed": 42},
            "sampling": {
                "mode": "2d",
                "dimensions": 2,
                "size": [512, 512]
            }
        }))
        .send()
        .await
        .unwrap();

    let elapsed = start.elapsed();
    assert_eq!(response.status(), 201);

    let result: serde_json::Value = response.json().await.unwrap();
    let data = result["data"].as_array().unwrap();
    assert_eq!(data.len(), 512);
    assert_eq!(data[0].as_array().unwrap().len(), 512);

    assert!(
        elapsed.as_secs() < 30,
        "512×512 grid generation took too long: {:?}",
        elapsed
    );

    println!("Performance test (512×512): {:?}", elapsed);
}
