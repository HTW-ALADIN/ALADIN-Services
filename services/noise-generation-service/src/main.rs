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
    #[serde(rename = "cellular")]
    Cellular {
        backend: String,
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
    (StatusCode::CREATED, Json(NoiseField {
        id: "nsf_123".to_string(),
        status: "completed".to_string(),
        algorithm: "perlin".to_string(),
    }))
}

async fn get_noise(Path(field_id): Path<String>) -> String {
    format!("Get noise field {}", field_id)
}
