mod cli;
use axum::{
    routing::{get, post},
    Router,
    Json,
    extract::{Path, State, Query},
    http::StatusCode,
};
use serde::{Deserialize, Serialize};
use tokio::net::TcpListener;
use clap::Parser;
use cli::{Cli, Commands};
use noise::{NoiseFn, Perlin, Simplex, SuperSimplex, OpenSimplex, Worley};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

#[derive(Clone)]
struct AppState {
    fields: Arc<Mutex<HashMap<String, Vec<Vec<f64>>>>>,
}

#[derive(Serialize, Deserialize, Debug)]
struct Sampling {
    mode: String,
    dimensions: i32,
    size: Option<Vec<usize>>,
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
    #[serde(rename = "opensimplex2")]
    OpenSimplex2 {
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
    #[serde(rename = "cellular")]
    Cellular {
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

    let state = AppState {
        fields: Arc::new(Mutex::new(HashMap::new())),
    };

    let app = Router::new()
        .route("/v1/algorithms", get(list_algorithms))
        .route("/v1/noise", post(generate_noise))
        .route("/v1/noise/:fieldId", get(get_noise))
        .route("/v1/noise/:fieldId/point", get(get_noise_point))
        .with_state(state);

    let listener = TcpListener::bind("0.0.0.0:8000").await.unwrap();
    println!("Listening on port 8000");
    axum::serve(listener, app).await.unwrap();
}

async fn list_algorithms() -> Json<serde_json::Value> {
    Json(serde_json::json!([
        {"algorithm": "perlin", "backend": "fastnoise_lite"},
        {"algorithm": "perlin", "backend": "noise_rs"},
        {"algorithm": "simplex", "backend": "noise_rs"},
        {"algorithm": "opensimplex2", "backend": "fastnoise_lite"},
        {"algorithm": "opensimplex2", "backend": "noise_rs"},
        {"algorithm": "supersimplex", "backend": "noise_rs"},
        {"algorithm": "value", "backend": "fastnoise_lite"},
        {"algorithm": "value", "backend": "noise_rs"},
        {"algorithm": "cellular", "backend": "fastnoise_lite"},
        {"algorithm": "cellular", "backend": "noise_rs"},
        {"algorithm": "fbm", "backend": "fastnoise_lite"},
        {"algorithm": "fbm", "backend": "noise_rs"},
        {"algorithm": "billow", "backend": "noise_rs"},
        {"algorithm": "ridged_multi", "backend": "fastnoise_lite"},
        {"algorithm": "ridged_multi", "backend": "noise_rs"},
        {"algorithm": "hybrid_multi", "backend": "noise_rs"},
        {"algorithm": "pingpong", "backend": "fastnoise_lite"},
        {"algorithm": "pingpong", "backend": "noise_rs"},
        {"algorithm": "domain_warp", "backend": "fastnoise_lite"},
        {"algorithm": "domain_warp", "backend": "noise_rs"},
        {"algorithm": "combinator", "backend": "noise_rs"},
        {"algorithm": "utility", "backend": "noise_rs"}
    ]))
}

async fn generate_noise(
    State(state): State<AppState>,
    Json(payload): Json<GenerateNoiseRequest>,
) -> (StatusCode, Json<NoiseField>) {
    let algorithm_name = match &payload {
        GenerateNoiseRequest::Perlin { backend: _, .. } => "perlin".to_string(),
        GenerateNoiseRequest::Simplex { .. } => "simplex".to_string(),
        GenerateNoiseRequest::OpenSimplex2 { .. } => "opensimplex2".to_string(),
        GenerateNoiseRequest::SuperSimplex { .. } => "supersimplex".to_string(),
        GenerateNoiseRequest::Value { .. } => "value".to_string(),
        GenerateNoiseRequest::Cellular { .. } => "cellular".to_string(),
        GenerateNoiseRequest::Fbm { .. } => "fbm".to_string(),
        GenerateNoiseRequest::Billow { .. } => "billow".to_string(),
        GenerateNoiseRequest::RidgedMulti { .. } => "ridged_multi".to_string(),
        GenerateNoiseRequest::HybridMulti { .. } => "hybrid_multi".to_string(),
        GenerateNoiseRequest::PingPong { .. } => "pingpong".to_string(),
        GenerateNoiseRequest::DomainWarp { .. } => "domain_warp".to_string(),
        GenerateNoiseRequest::Combinator { .. } => "combinator".to_string(),
        GenerateNoiseRequest::Utility { .. } => "utility".to_string(),
    };

    let field_id = format!("nsf_{}", uuid::Uuid::new_v4());
    
    let size = match &payload {
        GenerateNoiseRequest::Perlin { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Simplex { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::OpenSimplex2 { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::SuperSimplex { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Value { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Cellular { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Fbm { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Billow { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::RidgedMulti { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::HybridMulti { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::PingPong { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::DomainWarp { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Combinator { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Utility { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
    };
    
    let mut field = vec![vec![0.0; size[0]]; size[1]];
    
    match &payload {
        GenerateNoiseRequest::Perlin { backend, .. } => {
            let perlin = Perlin::new(1);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = perlin.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        },
        GenerateNoiseRequest::Simplex { .. } => {
            let simplex = Simplex::new(1);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = simplex.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        },
        GenerateNoiseRequest::OpenSimplex2 { .. } => {
            let opensimplex = OpenSimplex::new(1);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = opensimplex.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        },
        _ => {
            // Default to Perlin for now if not implemented
            let perlin = Perlin::new(1);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = perlin.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        }
    }

    state.fields.lock().unwrap().insert(field_id.clone(), field);
    
    (StatusCode::CREATED, Json(NoiseField {
        id: field_id,
        status: "completed".to_string(),
        algorithm: algorithm_name,
    }))
}

async fn get_noise(
    State(state): State<AppState>,
    Path(field_id): Path<String>,
) -> Result<Json<Vec<Vec<f64>>>, StatusCode> {
    let fields = state.fields.lock().unwrap();
    if let Some(field) = fields.get(&field_id) {
        Ok(Json(field.clone()))
    } else {
        Err(StatusCode::NOT_FOUND)
    }
}

#[derive(Deserialize)]
struct PointQuery {
    x: usize,
    y: usize,
}

async fn get_noise_point(
    State(state): State<AppState>,
    Path(field_id): Path<String>,
    Query(query): Query<PointQuery>,
) -> Result<Json<f64>, StatusCode> {
    let fields = state.fields.lock().unwrap();
    if let Some(field) = fields.get(&field_id) {
        if let Some(row) = field.get(query.y) {
            if let Some(value) = row.get(query.x) {
                Ok(Json(*value))
            } else {
                Err(StatusCode::BAD_REQUEST)
            }
        } else {
            Err(StatusCode::BAD_REQUEST)
        }
    } else {
        Err(StatusCode::NOT_FOUND)
    }
}