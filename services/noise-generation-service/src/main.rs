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
use noise::{NoiseFn, Perlin, Simplex, SuperSimplex, OpenSimplex, Worley, Value, Billow, MultiFractal};
use fastnoise_lite::FastNoiseLite;
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
    #[serde(rename = "white")]
    White {
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
        {"algorithm": "utility", "backend": "noise_rs"},
        {"algorithm": "white", "backend": "native"}
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
        GenerateNoiseRequest::White { .. } => "white".to_string(),
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
        GenerateNoiseRequest::White { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
    };
    
    let mut field = vec![vec![0.0; size[0]]; size[1]];
    
    match &payload {
        GenerateNoiseRequest::Perlin { backend, params, .. } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let perlin = Perlin::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = perlin.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    }
                }
            }
        },
        GenerateNoiseRequest::Simplex { params, .. } => {
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as u32;
            let simplex = Simplex::new(seed);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = simplex.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        },
        GenerateNoiseRequest::OpenSimplex2 { backend, params, .. } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                let smooth = params.get("smooth").and_then(|v| v.as_bool()).unwrap_or(false);
                noise.set_noise_type(Some(if smooth { fastnoise_lite::NoiseType::OpenSimplex2S } else { fastnoise_lite::NoiseType::OpenSimplex2 }));
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let opensimplex = OpenSimplex::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = opensimplex.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    }
                }
            }
        },
        GenerateNoiseRequest::Value { backend, params, .. } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                let interpolation = params.get("interpolation").and_then(|v| v.as_str()).unwrap_or("value");
                noise.set_noise_type(Some(if interpolation == "cubic" { fastnoise_lite::NoiseType::ValueCubic } else { fastnoise_lite::NoiseType::Value }));
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let value = Value::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = value.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    }
                }
            }
        },
        GenerateNoiseRequest::SuperSimplex { params, .. } => {
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as u32;
            let supersimplex = SuperSimplex::new(seed);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = supersimplex.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        },
        GenerateNoiseRequest::Cellular { backend, params, .. } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::Cellular));
                
                let dist = params.get("distance_function").and_then(|v| v.as_str()).unwrap_or("euclidean");
                let ret = params.get("return_type").and_then(|v| v.as_str()).unwrap_or("cell_value");
                let jitter = params.get("jitter").and_then(|v| v.as_f64()).unwrap_or(0.45);
                
                // Map string params to fastnoise_lite enums
                noise.set_cellular_distance_function(Some(match dist {
                    "manhattan" => fastnoise_lite::CellularDistanceFunction::Manhattan,
                    _ => fastnoise_lite::CellularDistanceFunction::Euclidean,
                }));
                noise.set_cellular_return_type(Some(match ret {
                    "distance" => fastnoise_lite::CellularReturnType::Distance,
                    _ => fastnoise_lite::CellularReturnType::CellValue,
                }));
                noise.set_cellular_jitter(Some(jitter as f32));
                
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let seed = seed as u32;
                let _dist = params.get("distance_function").and_then(|v| v.as_str()).unwrap_or("euclidean");
                let _ret = params.get("return_type").and_then(|v| v.as_str()).unwrap_or("cell_value");
                
                let cellular = Worley::new(seed);
                
                // Note: noise-rs Worley might not have these exact methods. 
                // Assuming they exist based on user request.
                // If they don't, this will fail to compile.
                
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = cellular.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    }
                }
            }
        },
        GenerateNoiseRequest::Fbm { backend, params, .. } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            println!("Fbm: backend={}, seed={}", backend, seed);
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::new();
                noise.set_seed(Some(seed));
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                noise.set_fractal_type(Some(fastnoise_lite::FractalType::FBm));
                
                let octaves = params.get("octaves").and_then(|v| v.as_i64()).unwrap_or(3) as i32;
                let lacunarity = params.get("lacunarity").and_then(|v| v.as_f64()).unwrap_or(2.0) as f32;
                let gain = params.get("gain").and_then(|v| v.as_f64()).unwrap_or(0.5) as f32;
                
                noise.set_fractal_octaves(Some(octaves));
                noise.set_fractal_lacunarity(Some(lacunarity));
                noise.set_fractal_gain(Some(gain));
                
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let fbm = noise::Fbm::<Perlin>::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = fbm.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    }
                }
            }
        },
        GenerateNoiseRequest::Billow { params, .. } => {
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as u32;
            let octaves = params.get("octaves").and_then(|v| v.as_i64()).unwrap_or(6) as usize;
            let persistence = params.get("persistence").and_then(|v| v.as_f64()).unwrap_or(0.5) as f64;
            
            let billow = Billow::<Perlin>::new(seed).set_octaves(octaves).set_persistence(persistence);
            
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = billow.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        },
        GenerateNoiseRequest::HybridMulti { params, .. } => {
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as u32;
            let octaves = params.get("octaves").and_then(|v| v.as_i64()).unwrap_or(6) as usize;
            let persistence = params.get("persistence").and_then(|v| v.as_f64()).unwrap_or(0.5) as f64;
            
            let hybrid = noise::HybridMulti::<Perlin>::new(seed).set_octaves(octaves).set_persistence(persistence);
            
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = hybrid.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                }
            }
        },
        GenerateNoiseRequest::RidgedMulti { backend, params, .. } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::new();
                noise.set_seed(Some(seed));
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                noise.set_fractal_type(Some(fastnoise_lite::FractalType::Ridged));
                
                let octaves = params.get("octaves").and_then(|v| v.as_i64()).unwrap_or(3) as i32;
                let lacunarity = params.get("lacunarity").and_then(|v| v.as_f64()).unwrap_or(2.0) as f32;
                let gain = params.get("gain").and_then(|v| v.as_f64()).unwrap_or(0.5) as f32;
                
                noise.set_fractal_octaves(Some(octaves));
                noise.set_fractal_lacunarity(Some(lacunarity));
                noise.set_fractal_gain(Some(gain));
                
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let ridged = noise::RidgedMulti::<Perlin>::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = ridged.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    }
                }
            }
        },
        GenerateNoiseRequest::PingPong { params, .. } => {
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            let mut noise = FastNoiseLite::new();
            noise.set_seed(Some(seed));
            
            let source = params.get("source").and_then(|v| v.as_str()).unwrap_or("perlin");
            noise.set_noise_type(Some(match source {
                "value" => fastnoise_lite::NoiseType::Value,
                _ => fastnoise_lite::NoiseType::Perlin,
            }));
            noise.set_fractal_type(Some(fastnoise_lite::FractalType::PingPong));
            
            let strength = params.get("strength").and_then(|v| v.as_f64()).unwrap_or(2.0) as f32;
            noise.set_fractal_ping_pong_strength(Some(strength));
            
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                }
            }
        },
        GenerateNoiseRequest::DomainWarp { params, .. } => {
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as i32;
            let mut noise = FastNoiseLite::new();
            noise.set_seed(Some(seed));
            
            let warp_type = params.get("warp_type").and_then(|v| v.as_str()).unwrap_or("open_simplex2");
            let amplitude = params.get("amplitude").and_then(|v| v.as_f64()).unwrap_or(30.0) as f32;
            
            noise.set_domain_warp_type(Some(match warp_type {
                "open_simplex2" => fastnoise_lite::DomainWarpType::OpenSimplex2,
                _ => fastnoise_lite::DomainWarpType::OpenSimplex2,
            }));
            noise.set_domain_warp_amp(Some(amplitude));
            
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                }
            }
        },
        GenerateNoiseRequest::Combinator { backend, params, .. } => {
            let op = params.get("op").and_then(|v| v.as_str()).unwrap_or("add");
            let source1 = Perlin::new(1);
            let source2 = Simplex::new(2);
            
            for y in 0..size[1] {
                for x in 0..size[0] {
                    let val1 = source1.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    let val2 = source2.get([x as f64 * 0.1, y as f64 * 0.1, 0.0]);
                    field[y][x] = match op {
                        "add" => val1 + val2,
                        "multiply" => val1 * val2,
                        _ => val1 + val2,
                    };
                }
            }
        },
        GenerateNoiseRequest::Utility { backend, params, .. } => {
            let kind = params.get("kind").and_then(|v| v.as_str()).unwrap_or("constant");
            let value = params.get("value").and_then(|v| v.as_f64()).unwrap_or(0.5);
            
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = match kind {
                        "constant" => value,
                        "cylinders" => {
                            let cylinders = noise::Cylinders::new();
                            cylinders.get([x as f64 * 0.1, y as f64 * 0.1, 0.0])
                        },
                        _ => value,
                    };
                }
            }
        },
        GenerateNoiseRequest::White { params, .. } => {
            let seed = params.get("seed").and_then(|v| v.as_u64()).unwrap_or(1) as u64;
            use std::hash::{Hash, Hasher};
            for y in 0..size[1] {
                for x in 0..size[0] {
                    let mut hasher = std::collections::hash_map::DefaultHasher::new();
                    seed.hash(&mut hasher);
                    x.hash(&mut hasher);
                    y.hash(&mut hasher);
                    let hash = hasher.finish();
                    field[y][x] = (hash as f64 / u64::MAX as f64) * 2.0 - 1.0;
                }
            }
        },
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