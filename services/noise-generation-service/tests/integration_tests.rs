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
async fn test_supersimplex_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "supersimplex",
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
async fn test_cellular_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "cellular",
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
async fn test_fbm_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "fbm",
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
async fn test_billow_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "billow",
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
async fn test_ridged_multi_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "ridged_multi",
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
async fn test_hybrid_multi_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "hybrid_multi",
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
async fn test_pingpong_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "pingpong",
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
async fn test_domain_warp_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "domain_warp",
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
async fn test_combinator_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "combinator",
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
async fn test_utility_generation() {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/v1/noise")
        .json(&json!({
            "algorithm": "utility",
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
async fn test_retrieve_noise_field() {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:8000/v1/noise/nsf_123")
        .send()
        .await
        .unwrap();
    
    assert_eq!(response.status(), 200);
}