use serde_json::json;

#[tokio::test]
async fn test_perlin_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "perlin",
            "backend": "fastnoise_lite",
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
            "backend": "noise_rs",
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
    
    let noise_field: serde_json::Value = response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();

    // Retrieve and verify the field
    let get_response = client
        .get(format!("http://localhost:8000/v1/noise/{}", field_id))
        .send()
        .await
        .unwrap();
    
    assert_eq!(get_response.status(), 200);
    let field_data: Vec<Vec<f64>> = get_response.json().await.unwrap();
    assert_eq!(field_data.len(), 5);
    assert_eq!(field_data[0].len(), 5);
}

#[tokio::test]
async fn test_opensimplex2_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "opensimplex2",
            "backend": "fastnoise_lite",
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
    
    let noise_field: serde_json::Value = response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();

    // Retrieve and verify the field
    let get_response = client
        .get(format!("http://localhost:8000/v1/noise/{}", field_id))
        .send()
        .await
        .unwrap();
    
    assert_eq!(get_response.status(), 200);
    let field_data: Vec<Vec<f64>> = get_response.json().await.unwrap();
    assert_eq!(field_data.len(), 5);
    assert_eq!(field_data[0].len(), 5);
}

#[tokio::test]
async fn test_supersimplex_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "supersimplex",
            "backend": "noise_rs",
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
    
    let noise_field: serde_json::Value = response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();

    // Retrieve and verify the field
    let get_response = client
        .get(format!("http://localhost:8000/v1/noise/{}", field_id))
        .send()
        .await
        .unwrap();
    
    assert_eq!(get_response.status(), 200);
    let field_data: Vec<Vec<f64>> = get_response.json().await.unwrap();
    assert_eq!(field_data.len(), 5);
    assert_eq!(field_data[0].len(), 5);
}

#[tokio::test]
async fn test_value_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "value",
            "backend": "fastnoise_lite",
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
    
    let noise_field: serde_json::Value = response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();

    // Retrieve and verify the field
    let get_response = client
        .get(format!("http://localhost:8000/v1/noise/{}", field_id))
        .send()
        .await
        .unwrap();
    
    assert_eq!(get_response.status(), 200);
    let field_data: Vec<Vec<f64>> = get_response.json().await.unwrap();
    assert_eq!(field_data.len(), 5);
    assert_eq!(field_data[0].len(), 5);
}

#[tokio::test]
async fn test_cellular_parameters() {
    let client = reqwest::Client::new();
    
    // Generate field 1: Euclidean, CellValue, Jitter 0.45
    let resp1 = client.post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "cellular",
            "backend": "fastnoise_lite",
            "params": {"distance_function": "euclidean", "return_type": "cell_value", "jitter": 0.45},
            "sampling": {"mode": "grid", "dimensions": 2, "size": [5, 5]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send().await.unwrap();
    let id1 = resp1.json::<serde_json::Value>().await.unwrap()["id"].as_str().unwrap().to_string();
    let field1: Vec<Vec<f64>> = client.get(format!("http://localhost:8000/v1/noise/{}", id1)).send().await.unwrap().json().await.unwrap();

    // Generate field 2: Manhattan, Distance, Jitter 0.9
    let resp2 = client.post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "cellular",
            "backend": "fastnoise_lite",
            "params": {"distance_function": "manhattan", "return_type": "distance", "jitter": 0.9},
            "sampling": {"mode": "grid", "dimensions": 2, "size": [5, 5]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send().await.unwrap();
    let id2 = resp2.json::<serde_json::Value>().await.unwrap()["id"].as_str().unwrap().to_string();
    let field2: Vec<Vec<f64>> = client.get(format!("http://localhost:8000/v1/noise/{}", id2)).send().await.unwrap().json().await.unwrap();

    // Assert fields are different
    assert_ne!(field1, field2);
}

#[tokio::test]
async fn test_fbm_seed_parameter() {
    let client = reqwest::Client::new();
    
    // Generate field 1: Seed 1
    let params1 = json!({"seed": 1, "octaves": 3});
    println!("Params1: {}", params1);
    let resp1 = client.post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "fbm",
            "backend": "fastnoise_lite",
            "params": params1,
            "sampling": {"mode": "grid", "dimensions": 2, "size": [20, 20]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send().await.unwrap();
    let id1 = resp1.json::<serde_json::Value>().await.unwrap()["id"].as_str().unwrap().to_string();
    let field1: Vec<Vec<f64>> = client.get(format!("http://localhost:8000/v1/noise/{}", id1)).send().await.unwrap().json().await.unwrap();

    // Generate field 2: Seed 2
    let params2 = json!({"seed": 2, "octaves": 4});
    println!("Params2: {}", params2);
    let resp2 = client.post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "fbm",
            "backend": "fastnoise_lite",
            "params": params2,
            "sampling": {"mode": "grid", "dimensions": 2, "size": [20, 20]},
            "output": {"format": "json", "normalize": "none"}
        }))
        .send().await.unwrap();
    let id2 = resp2.json::<serde_json::Value>().await.unwrap()["id"].as_str().unwrap().to_string();
    let field2: Vec<Vec<f64>> = client.get(format!("http://localhost:8000/v1/noise/{}", id2)).send().await.unwrap().json().await.unwrap();

    // Assert fields are significantly different
    let mut diff = 0.0;
    for y in 0..20 {
        for x in 0..20 {
            diff += (field1[y][x] - field2[y][x]).abs();
        }
    }
    let mean_diff = diff / (20.0 * 20.0);
    assert!(mean_diff > 0.01, "Fields should be significantly different, mean_diff: {}", mean_diff);
}

#[tokio::test]
async fn test_billow_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "billow",
            "backend": "noise_rs",
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
            "backend": "fastnoise_lite",
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
            "backend": "noise_rs",
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
            "backend": "fastnoise_lite",
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
            "backend": "fastnoise_lite",
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
            "backend": "noise_rs",
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
    
    let noise_field: serde_json::Value = response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();

    // Retrieve and verify the field
    let get_response = client
        .get(format!("http://localhost:8000/v1/noise/{}", field_id))
        .send()
        .await
        .unwrap();
    
    assert_eq!(get_response.status(), 200);
    let field_data: Vec<Vec<f64>> = get_response.json().await.unwrap();
    assert_eq!(field_data.len(), 5);
    assert_eq!(field_data[0].len(), 5);
}

#[tokio::test]
async fn test_utility_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "utility",
            "backend": "noise_rs",
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
    
    let noise_field: serde_json::Value = response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();

    // Retrieve and verify the field
    let get_response = client
        .get(format!("http://localhost:8000/v1/noise/{}", field_id))
        .send()
        .await
        .unwrap();
    
    assert_eq!(get_response.status(), 200);
    let field_data: Vec<Vec<f64>> = get_response.json().await.unwrap();
    assert_eq!(field_data.len(), 5);
    assert_eq!(field_data[0].len(), 5);
    assert_eq!(field_data[0][0], 0.5);
}

#[tokio::test]
async fn test_get_noise_point() {
    let client = reqwest::Client::new();
    
    // 1. Generate a field
    let gen_response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "perlin",
            "backend": "fastnoise_lite",
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
    
    assert_eq!(gen_response.status(), 201);
    
    let noise_field: serde_json::Value = gen_response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();

    // 2. Query a specific point
    let response = client
        .get(format!("http://localhost:8000/v1/noise/{}/point?x=1&y=2", field_id))
        .send()
        .await
        .unwrap();
    
    assert_eq!(response.status(), 200);
    let point_value: f64 = response.json().await.unwrap();
    // Just check if it's a valid number
    assert!(point_value.is_finite());
}
#[tokio::test]
async fn test_white_noise_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "white",
            "params": {
                "seed": 123
            },
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
    
    let noise_field: serde_json::Value = response.json().await.unwrap();
    let field_id = noise_field["id"].as_str().unwrap();
    
    // Verify we can retrieve the field
    let get_response = client
        .get(format!("http://localhost:8000/v1/noise/{}", field_id))
        .send()
        .await
        .unwrap();
        
    assert_eq!(get_response.status(), 200);
    let field: Vec<Vec<f64>> = get_response.json().await.unwrap();
    assert_eq!(field.len(), 5);
    assert_eq!(field[0].len(), 5);
}
