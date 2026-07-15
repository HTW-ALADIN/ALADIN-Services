mod cli;
use axum::{
    routing::{get, post},
    Router,
    Json,
    extract::Path,
    http::StatusCode,
};
use serde::{Deserialize, Serialize};
use tokio::net::TcpListener;
use clap::Parser;
use cli::{Cli, Commands};
use noise::{NoiseFn, Perlin, Simplex, SuperSimplex, Value};

#[derive(Serialize, Deserialize, Debug)]
struct Sampling {
    mode: String,
    dimensions: i32,
    grid: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug)]
struct Output {
    format: String,
    normalize: String,
}

#[derive(Serialize, Deserialize, Debug)]
#[serde(tag = "algorithm")]
enum GenerateNoiseRequest {
    #[serde(rename = "perlin")]
    Perlin {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "simplex")]
    Simplex {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "supersimplex")]
    SuperSimplex {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "value")]
    Value {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "fbm")]
    Fbm {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "billow")]
    Billow {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "ridged_multi")]
    RidgedMulti {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "hybrid_multi")]
    HybridMulti {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "pingpong")]
    PingPong {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "domain_warp")]
    DomainWarp {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "combinator")]
    Combinator {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "utility")]
    Utility {
        backend: Option<String>,
        params: serde_json::Value,
        sampling: Sampling,
        output: Option<Output>,
    },
}

#[derive(Serialize, Debug)]
struct NoiseField {
    id: String,
    status: String,
    algorithm: String,
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    if let Some(command) = cli.command {
        match command {
            Commands::Generate { algorithm, backend } => {
                println!("Generating noise with algorithm: {}, backend: {:?}", algorithm, backend);
                return;
            }
        }
    }

    let app = Router::new()
        .route("/v1/algorithms", get(list_algorithms))
        .route("/v1/noise", post(generate_noise))
        .route("/v1/noise/:fieldId", get(get_noise));

    let listener = TcpListener::bind("0.0.0.0:3000").await.unwrap();
    println!("Listening on port 3000");
    axum::serve(listener, app).await.unwrap();
}

async fn list_algorithms() -> Json<serde_json::Value> {
    Json(serde_json::json!([{"algorithm": "perlin", "backend": "fastnoise_lite"}]))
}

async fn generate_noise(Json(payload): Json<GenerateNoiseRequest>) -> (StatusCode, Json<NoiseField>) {
    println!("Received request: {:?}", payload);
    // In a real implementation, this would actually generate noise based on the algorithm
    // For now, we'll just return a dummy response
    (StatusCode::CREATED, Json(NoiseField {
        id: "nsf_123".to_string(),
        status: "completed".to_string(),
        algorithm: match &payload {
            GenerateNoiseRequest::Perlin { .. } => "perlin".to_string(),
            GenerateNoiseRequest::Simplex { .. } => "simplex".to_string(),
            GenerateNoiseRequest::SuperSimplex { .. } => "supersimplex".to_string(),
            GenerateNoiseRequest::Value { .. } => "value".to_string(),
            GenerateNoiseRequest::Fbm { .. } => "fbm".to_string(),
            GenerateNoiseRequest::Billow { .. } => "billow".to_string(),
            GenerateNoiseRequest::RidgedMulti { .. } => "ridged_multi".to_string(),
            GenerateNoiseRequest::HybridMulti { .. } => "hybrid_multi".to_string(),
            GenerateNoiseRequest::PingPong { .. } => "pingpong".to_string(),
            GenerateNoiseRequest::DomainWarp { .. } => "domain_warp".to_string(),
            GenerateNoiseRequest::Combinator { .. } => "combinator".to_string(),
            GenerateNoiseRequest::Utility { .. } => "utility".to_string(),
        },
    }))
}

async fn get_noise(Path(field_id): Path<String>) -> String {
    format!("Get noise field {}", field_id)
}

fn generate_perlin_noise(x: f64, y: f64) -> f64 {
    let perlin = Perlin::new(1);
    perlin.get([x, y, 0.0])
}

fn generate_simplex_noise(x: f64, y: f64) -> f64 {
    let simplex = Simplex::new(1);
    simplex.get([x, y, 0.0])
}

fn generate_supersimplex_noise(x: f64, y: f64) -> f64 {
    let supersimplex = SuperSimplex::new(1);
    supersimplex.get([x, y, 0.0])
}

fn generate_value_noise(x: f64, y: f64) -> f64 {
    let value = Value::new(1);
    value.get([x, y, 0.0])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_perlin_generation() {
        let noise = generate_perlin_noise(0.5, 0.5);
        assert!(noise >= -1.0 && noise <= 1.0);
    }

    #[test]
    fn test_simplex_generation() {
        let noise = generate_simplex_noise(0.5, 0.5);
        assert!(noise >= -1.0 && noise <= 1.0);
    }

    #[test]
    fn test_supersimplex_generation() {
        let noise = generate_supersimplex_noise(0.5, 0.5);
        assert!(noise >= -1.0 && noise <= 1.0);
    }

    #[test]
    fn test_value_generation() {
        let noise = generate_value_noise(0.5, 0.5);
        assert!(noise >= -1.0 && noise <= 1.0);
    }

    #[test]
    fn test_fbm_generation() {
        // Placeholder for fbm noise test
        assert_eq!(1, 1);
    }

    #[test]
    fn test_billow_generation() {
        // Placeholder for billow noise test
        assert_eq!(1, 1);
    }

    #[test]
    fn test_ridged_multi_generation() {
        // Placeholder for ridged multi noise test
        assert_eq!(1, 1);
    }

    #[test]
    fn test_hybrid_multi_generation() {
        // Placeholder for hybrid multi noise test
        assert_eq!(1, 1);
    }

    #[test]
    fn test_pingpong_generation() {
        // Placeholder for pingpong noise test
        assert_eq!(1, 1);
    }

    #[test]
    fn test_domain_warp_generation() {
        // Placeholder for domain warp test
        assert_eq!(1, 1);
    }

    #[test]
    fn test_combinator_generation() {
        // Placeholder for combinator test
        assert_eq!(1, 1);
    }

    #[test]
    fn test_utility_generation() {
        // Placeholder for utility generator test
        assert_eq!(1, 1);
    }
}
