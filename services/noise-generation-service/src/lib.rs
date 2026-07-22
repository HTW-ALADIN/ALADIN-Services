// Range loops and casts are clearer for noise generation — keep them explicit
#![allow(clippy::needless_range_loop, clippy::unnecessary_cast)]

use axum::{http::StatusCode, Json};
use fastnoise_lite::FastNoiseLite;
use noise::{
    Add, Blend, Constant, Cylinders, HybridMulti, Max, Min, MultiFractal, Multiply, NoiseFn,
    OpenSimplex, Perlin, Simplex, SuperSimplex, Value, Worley,
};
use serde::{Deserialize, Serialize};
use utoipa::{OpenApi, ToSchema};

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct SeedParams {
    pub seed: Option<u64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct CellularParams {
    pub seed: Option<u64>,
    pub distance_function: Option<CellularDistanceFunction>,
    pub return_type: Option<CellularReturnType>,
    pub jitter: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum CellularDistanceFunction {
    Euclidean,
    EuclideanSq,
    Manhattan,
    Hybrid,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum CellularReturnType {
    CellValue,
    Distance,
    Distance2,
    Distance2Add,
    Distance2Sub,
    Distance2Mul,
    Distance2Div,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct FractalParams {
    pub seed: Option<u64>,
    pub octaves: Option<usize>,
    pub frequency: Option<f64>,
    pub lacunarity: Option<f64>,
    pub persistence: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct RidgedMultiParams {
    pub seed: Option<u64>,
    pub octaves: Option<usize>,
    pub frequency: Option<f64>,
    pub lacunarity: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct PingPongParams {
    pub seed: Option<u64>,
    pub strength: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct DomainWarpParams {
    pub seed: Option<u64>,
    pub amplitude: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct CombinatorParams {
    pub seed: Option<u64>,
    pub op: Option<CombinatorOp>,
    pub blend_factor: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum CombinatorOp {
    Add,
    Multiply,
    Min,
    Max,
    Blend,
}

impl Default for CombinatorOp {
    fn default() -> Self {
        Self::Add
    }
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct UtilityParams {
    pub kind: Option<UtilityKind>,
    pub value: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum UtilityKind {
    Constant,
    Cylinders,
}

impl Default for UtilityKind {
    fn default() -> Self {
        Self::Constant
    }
}

#[derive(OpenApi)]
#[openapi(
    paths(
        list_algorithms,
        generate_noise
    ),
    components(
        schemas(
            GenerateNoiseRequest,
            Sampling,
            Output,
            NoiseFieldResult,
            AlgorithmEntry,
            SeedParams,
            CellularParams,
            CellularDistanceFunction,
            CellularReturnType,
            FractalParams,
            RidgedMultiParams,
            PingPongParams,
            DomainWarpParams,
            CombinatorParams,
            CombinatorOp,
            UtilityParams,
            UtilityKind
        )
    ),
    tags(
        (name = "noise", description = "Noise generation API")
    )
)]
pub struct ApiDoc;

#[derive(Serialize, Deserialize, Debug, ToSchema)]
pub struct Sampling {
    pub mode: String,
    pub dimensions: i32,
    pub size: Option<Vec<usize>>,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
pub struct Output {
    pub format: String,
    pub normalize: String,
}

#[derive(Serialize, Deserialize, Debug, ToSchema)]
#[serde(tag = "algorithm")]
pub enum GenerateNoiseRequest {
    #[serde(rename = "perlin")]
    Perlin {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "simplex")]
    Simplex {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "opensimplex2")]
    OpenSimplex2 {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "supersimplex")]
    SuperSimplex {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "value")]
    Value {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "cellular")]
    Cellular {
        #[serde(default)]
        params: CellularParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "fbm")]
    Fbm {
        #[serde(default)]
        params: FractalParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "billow")]
    Billow {
        #[serde(default)]
        params: FractalParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "ridged_multi")]
    RidgedMulti {
        #[serde(default)]
        params: RidgedMultiParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "hybrid_multi")]
    HybridMulti {
        #[serde(default)]
        params: RidgedMultiParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "pingpong")]
    PingPong {
        #[serde(default)]
        params: PingPongParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "domain_warp")]
    DomainWarp {
        #[serde(default)]
        params: DomainWarpParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "combinator")]
    Combinator {
        #[serde(default)]
        params: CombinatorParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "utility")]
    Utility {
        #[serde(default)]
        params: UtilityParams,
        sampling: Sampling,
        output: Option<Output>,
    },
    #[serde(rename = "white")]
    White {
        #[serde(default)]
        params: SeedParams,
        sampling: Sampling,
        output: Option<Output>,
    },
}

#[derive(Serialize, Debug, ToSchema)]
pub struct NoiseFieldResult {
    pub id: String,
    pub status: String,
    pub algorithm: String,
    pub data: Vec<Vec<f64>>,
    pub size: Vec<usize>,
}

#[derive(Serialize, Debug, ToSchema)]
pub struct AlgorithmEntry {
    pub algorithm: String,
    pub backend: String,
}

#[utoipa::path(
    get,
    path = "/v1/algorithms",
    tag = "noise",
    responses(
        (status = 200, description = "List of algorithms", body = Vec<String>)
    )
)]
pub async fn list_algorithms() -> Json<serde_json::Value> {
    Json(serde_json::json!([
        "perlin",
        "simplex",
        "opensimplex2",
        "supersimplex",
        "value",
        "cellular",
        "fbm",
        "billow",
        "ridged_multi",
        "hybrid_multi",
        "pingpong",
        "domain_warp",
        "combinator",
        "utility",
        "white"
    ]))
}

#[utoipa::path(
    post,
    path = "/v1/noise",
    tag = "noise",
    request_body = GenerateNoiseRequest,
    responses(
        (status = 201, description = "Noise field created", body = NoiseFieldResult)
    )
)]
pub async fn generate_noise(
    Json(payload): Json<GenerateNoiseRequest>,
) -> (StatusCode, Json<NoiseFieldResult>) {
    let algorithm_name = match &payload {
        GenerateNoiseRequest::Perlin { .. } => "perlin".to_string(),
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
        GenerateNoiseRequest::Perlin { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::Simplex { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::OpenSimplex2 { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::SuperSimplex { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::Value { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::Cellular { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::Fbm { sampling, .. } => sampling.size.clone().unwrap_or(vec![10, 10]),
        GenerateNoiseRequest::Billow { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::RidgedMulti { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::HybridMulti { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::PingPong { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::DomainWarp { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::Combinator { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::Utility { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
        GenerateNoiseRequest::White { sampling, .. } => {
            sampling.size.clone().unwrap_or(vec![10, 10])
        }
    };

    let mut field = vec![vec![0.0; size[0]]; size[1]];

    match &payload {
        GenerateNoiseRequest::Perlin {
            backend, params, ..
        } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.seed.unwrap_or(1) as i32;
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
        }
        GenerateNoiseRequest::Simplex {
            backend, params, ..
        } => {
            let _backend = backend.as_deref().unwrap_or("noise_rs");
            let seed = params.seed.unwrap_or(1) as u32;
            let simplex = Simplex::new(seed);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = simplex.get([x as f64 * 0.1, y as f64 * 0.1]);
                }
            }
        }
        GenerateNoiseRequest::OpenSimplex2 {
            backend, params, ..
        } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.seed.unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::OpenSimplex2));
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let opensimplex = OpenSimplex::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = opensimplex.get([x as f64 * 0.1, y as f64 * 0.1]);
                    }
                }
            }
        }
        GenerateNoiseRequest::SuperSimplex {
            backend: _, params, ..
        } => {
            let seed = params.seed.unwrap_or(1) as u32;
            let supersimplex = SuperSimplex::new(seed);
            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = supersimplex.get([x as f64 * 0.1, y as f64 * 0.1]);
                }
            }
        }
        GenerateNoiseRequest::Value {
            backend, params, ..
        } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.seed.unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::Value));
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let value = Value::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = value.get([x as f64 * 0.1, y as f64 * 0.1]);
                    }
                }
            }
        }
        GenerateNoiseRequest::Cellular {
            backend, params, ..
        } => {
            let backend = backend.as_deref().unwrap_or("fastnoise_lite");
            let seed = params.seed.unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::Cellular));
                if let Some(dist_fn) = &params.distance_function {
                    noise.set_cellular_distance_function(Some(match dist_fn {
                        CellularDistanceFunction::Euclidean => {
                            fastnoise_lite::CellularDistanceFunction::Euclidean
                        }
                        CellularDistanceFunction::EuclideanSq => {
                            fastnoise_lite::CellularDistanceFunction::EuclideanSq
                        }
                        CellularDistanceFunction::Manhattan => {
                            fastnoise_lite::CellularDistanceFunction::Manhattan
                        }
                        CellularDistanceFunction::Hybrid => {
                            fastnoise_lite::CellularDistanceFunction::Hybrid
                        }
                    }));
                }
                if let Some(ret_type) = &params.return_type {
                    noise.set_cellular_return_type(Some(match ret_type {
                        CellularReturnType::CellValue => {
                            fastnoise_lite::CellularReturnType::CellValue
                        }
                        CellularReturnType::Distance => {
                            fastnoise_lite::CellularReturnType::Distance
                        }
                        CellularReturnType::Distance2 => {
                            fastnoise_lite::CellularReturnType::Distance2
                        }
                        CellularReturnType::Distance2Add => {
                            fastnoise_lite::CellularReturnType::Distance2Add
                        }
                        CellularReturnType::Distance2Sub => {
                            fastnoise_lite::CellularReturnType::Distance2Sub
                        }
                        CellularReturnType::Distance2Mul => {
                            fastnoise_lite::CellularReturnType::Distance2Mul
                        }
                        CellularReturnType::Distance2Div => {
                            fastnoise_lite::CellularReturnType::Distance2Div
                        }
                    }));
                }
                if let Some(jitter) = params.jitter {
                    noise.set_cellular_jitter(Some(jitter as f32));
                }
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let worley = Worley::new(seed as u32);
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = worley.get([x as f64 * 0.1, y as f64 * 0.1]);
                    }
                }
            }
        }
        GenerateNoiseRequest::Fbm {
            backend: _, params, ..
        } => {
            let seed = params.seed.unwrap_or(1) as u32;
            let octaves = params.octaves.unwrap_or(4);
            let frequency = params.frequency.unwrap_or(0.1);
            let lacunarity = params.lacunarity.unwrap_or(2.0);
            let persistence = params.persistence.unwrap_or(0.5);

            let fbm = noise::Fbm::<Perlin>::new(seed)
                .set_octaves(octaves)
                .set_frequency(frequency)
                .set_lacunarity(lacunarity)
                .set_persistence(persistence);

            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = fbm.get([x as f64 * 0.1, y as f64 * 0.1]);
                }
            }
        }
        GenerateNoiseRequest::Billow {
            backend: _, params, ..
        } => {
            let seed = params.seed.unwrap_or(1) as u32;
            let octaves = params.octaves.unwrap_or(4);
            let frequency = params.frequency.unwrap_or(0.1);
            let lacunarity = params.lacunarity.unwrap_or(2.0);
            let persistence = params.persistence.unwrap_or(0.5);

            let billow = noise::Billow::<Perlin>::new(seed)
                .set_octaves(octaves)
                .set_frequency(frequency)
                .set_lacunarity(lacunarity)
                .set_persistence(persistence);

            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = billow.get([x as f64 * 0.1, y as f64 * 0.1]);
                }
            }
        }
        GenerateNoiseRequest::RidgedMulti {
            backend, params, ..
        } => {
            let backend = backend.as_deref().unwrap_or("noise_rs");
            let seed = params.seed.unwrap_or(1) as i32;
            if backend == "fastnoise_lite" {
                let mut noise = FastNoiseLite::with_seed(seed);
                noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                noise.set_fractal_type(Some(fastnoise_lite::FractalType::Ridged));
                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                    }
                }
            } else {
                let octaves = params.octaves.unwrap_or(4);
                let frequency = params.frequency.unwrap_or(0.1);
                let lacunarity = params.lacunarity.unwrap_or(2.0);

                let ridged = noise::RidgedMulti::<Perlin>::new(seed as u32)
                    .set_octaves(octaves)
                    .set_frequency(frequency)
                    .set_lacunarity(lacunarity);

                for y in 0..size[1] {
                    for x in 0..size[0] {
                        field[y][x] = ridged.get([x as f64 * 0.1, y as f64 * 0.1]);
                    }
                }
            }
        }
        GenerateNoiseRequest::HybridMulti { params, .. } => {
            let seed = params.seed.unwrap_or(1) as u32;
            let octaves = params.octaves.unwrap_or(4);
            let frequency = params.frequency.unwrap_or(0.1);
            let lacunarity = params.lacunarity.unwrap_or(2.0);

            let hybrid = HybridMulti::<Perlin>::new(seed)
                .set_octaves(octaves)
                .set_frequency(frequency)
                .set_lacunarity(lacunarity);

            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = hybrid.get([x as f64 * 0.1, y as f64 * 0.1]);
                }
            }
        }
        GenerateNoiseRequest::PingPong {
            backend: _backend,
            params,
            ..
        } => {
            let seed = params.seed.unwrap_or(1) as i32;
            let strength = params.strength.unwrap_or(2.0);

            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_fractal_type(Some(fastnoise_lite::FractalType::PingPong));
            noise.set_fractal_ping_pong_strength(Some(strength as f32));
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));

            for y in 0..size[1] {
                for x in 0..size[0] {
                    field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
                }
            }
        }
        GenerateNoiseRequest::DomainWarp { params, .. } => {
            let seed = params.seed.unwrap_or(1) as i32;
            let amplitude = params.amplitude.unwrap_or(1.0);

            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_domain_warp_type(Some(fastnoise_lite::DomainWarpType::OpenSimplex2));
            noise.set_domain_warp_amp(Some(amplitude as f32));

            for y in 0..size[1] {
                for x in 0..size[0] {
                    let x_coord = x as f32;
                    let y_coord = y as f32;
                    let (warped_x, warped_y) = noise.domain_warp_2d(x_coord, y_coord);

                    // Use warped coordinates to sample base noise
                    let mut base_noise = FastNoiseLite::with_seed(seed + 1);
                    base_noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                    field[y][x] = base_noise.get_noise_2d(warped_x, warped_y) as f64;
                }
            }
        }
        GenerateNoiseRequest::Combinator { params, .. } => {
            let seed = params.seed.unwrap_or(1) as u32;
            let op = params.op.as_ref().unwrap_or(&CombinatorOp::Add);

            // Create two source noises for combination
            let source1 = Perlin::new(seed);
            let source2 = Perlin::new(seed + 1);

            for y in 0..size[1] {
                for x in 0..size[0] {
                    let pos = [x as f64 * 0.1, y as f64 * 0.1];

                    field[y][x] = match op {
                        CombinatorOp::Add => Add::new(source1, source2).get(pos),
                        CombinatorOp::Multiply => Multiply::new(source1, source2).get(pos),
                        CombinatorOp::Min => Min::new(source1, source2).get(pos),
                        CombinatorOp::Max => Max::new(source1, source2).get(pos),
                        CombinatorOp::Blend => {
                            let _blend_factor = params.blend_factor.unwrap_or(0.5);
                            let control = Perlin::new(seed + 2);
                            Blend::new(source1, source2, control).get(pos)
                        }
                    };
                }
            }
        }
        GenerateNoiseRequest::Utility { params, .. } => {
            let kind = params.kind.as_ref().unwrap_or(&UtilityKind::Constant);

            for y in 0..size[1] {
                for x in 0..size[0] {
                    let pos = [x as f64 * 0.1, y as f64 * 0.1];

                    field[y][x] = match kind {
                        UtilityKind::Constant => {
                            let value = params.value.unwrap_or(1.0);
                            Constant::new(value).get(pos)
                        }
                        UtilityKind::Cylinders => Cylinders::new().get(pos),
                    };
                }
            }
        }
        GenerateNoiseRequest::White { params, .. } => {
            let seed = params.seed.unwrap_or(1);

            for y in 0..size[1] {
                for x in 0..size[0] {
                    // Deterministic LCG (Lehmer random number generator)
                    // Stable across all platforms and Rust versions
                    let mut state = seed
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    state ^= (x as u64).wrapping_mul(374761393);
                    state ^= (y as u64).wrapping_mul(668265263);
                    state = state.wrapping_mul(12741261754838537793);
                    let hash = state ^ (state >> 31);
                    field[y][x] = (hash as f64 / u64::MAX as f64) * 2.0 - 1.0;
                }
            }
        }
    }

    (
        StatusCode::CREATED,
        Json(NoiseFieldResult {
            id: field_id,
            status: "completed".to_string(),
            algorithm: algorithm_name,
            data: field,
            size,
        }),
    )
}
