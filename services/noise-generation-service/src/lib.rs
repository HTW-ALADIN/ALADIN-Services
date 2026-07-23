// Range loops and casts are clearer for noise generation — keep them explicit
#![allow(clippy::needless_range_loop, clippy::unnecessary_cast)]

use axum::{http::StatusCode, Json};
use fastnoise_lite::FastNoiseLite;
use noise::{
    Add, Blend, Constant, Cylinders, HybridMulti, Max, Min, MultiFractal, Multiply, NoiseFn,
    Perlin, Simplex, SuperSimplex,
};
use serde::{Deserialize, Serialize};
use utoipa::{OpenApi, ToSchema};

// ─── Helpers ──────────────────────────────────────────────────────────────────

fn random_seed() -> u32 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    (nanos ^ (nanos >> 32)) as u32
}

fn get_seed(seed: Option<u32>) -> u32 {
    seed.unwrap_or_else(random_seed)
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct SeedParams {
    pub seed: Option<u32>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct CellularParams {
    pub seed: Option<u32>,
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
    pub seed: Option<u32>,
    pub octaves: Option<usize>,
    pub frequency: Option<f64>,
    pub lacunarity: Option<f64>,
    pub persistence: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct RidgedMultiParams {
    pub seed: Option<u32>,
    pub octaves: Option<usize>,
    pub frequency: Option<f64>,
    pub lacunarity: Option<f64>,
    pub persistence: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct PingPongParams {
    pub seed: Option<u32>,
    pub strength: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct DomainWarpParams {
    pub seed: Option<u32>,
    pub amplitude: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Default, ToSchema)]
pub struct CombinatorParams {
    pub seed: Option<u32>,
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
            OutputFormat,
            NoiseFieldResult,
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
    pub size: Option<Vec<usize>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum OutputFormat {
    Json,
    Csv,
}

impl Default for OutputFormat {
    fn default() -> Self {
        Self::Json
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, ToSchema)]
pub struct Output {
    pub format: OutputFormat,
    pub normalize: bool,
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
    // Extract algorithm name from the tagged enum (no manual match needed)
    let algorithm_name = payload.algorithm_name();

    let field_id = format!("nsf_{}", uuid::Uuid::new_v4());

    let size = payload.sampling_size().unwrap_or_else(|| vec![64, 64]);

    let mut field = vec![vec![0.0; size[0]]; size[1]];

    // --- Generate noise ----------------------------------------------------------
    generate_field(&mut field, &payload, &size);

    // --- Normalize (if requested) -------------------------------------------------
    let normalize = payload.should_normalize();
    if normalize {
        let mut min_val = f64::MAX;
        let mut max_val = f64::MIN;
        for row in &field {
            for &v in row {
                if v < min_val { min_val = v; }
                if v > max_val { max_val = v; }
            }
        }
        let range = max_val - min_val;
        if range > 0.0 {
            for row in &mut field {
                for v in row.iter_mut() {
                    *v = (*v - min_val) / range;
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

// ─── Algorithm name extraction via serde tag ──────────────────────────────────

impl GenerateNoiseRequest {
    fn algorithm_name(&self) -> String {
        // serde(tag = "algorithm") already stores the variant name in JSON
        // We can reconstruct it from the serialized form
        match self {
            GenerateNoiseRequest::Perlin { .. } => "perlin",
            GenerateNoiseRequest::Simplex { .. } => "simplex",
            GenerateNoiseRequest::OpenSimplex2 { .. } => "opensimplex2",
            GenerateNoiseRequest::SuperSimplex { .. } => "supersimplex",
            GenerateNoiseRequest::Value { .. } => "value",
            GenerateNoiseRequest::Cellular { .. } => "cellular",
            GenerateNoiseRequest::Fbm { .. } => "fbm",
            GenerateNoiseRequest::Billow { .. } => "billow",
            GenerateNoiseRequest::RidgedMulti { .. } => "ridged_multi",
            GenerateNoiseRequest::HybridMulti { .. } => "hybrid_multi",
            GenerateNoiseRequest::PingPong { .. } => "pingpong",
            GenerateNoiseRequest::DomainWarp { .. } => "domain_warp",
            GenerateNoiseRequest::Combinator { .. } => "combinator",
            GenerateNoiseRequest::Utility { .. } => "utility",
            GenerateNoiseRequest::White { .. } => "white",
        }
        .to_string()
    }

    fn sampling_size(&self) -> Option<Vec<usize>> {
        match self {
            GenerateNoiseRequest::Perlin { sampling, .. }
            | GenerateNoiseRequest::Simplex { sampling, .. }
            | GenerateNoiseRequest::OpenSimplex2 { sampling, .. }
            | GenerateNoiseRequest::SuperSimplex { sampling, .. }
            | GenerateNoiseRequest::Value { sampling, .. }
            | GenerateNoiseRequest::Cellular { sampling, .. }
            | GenerateNoiseRequest::Fbm { sampling, .. }
            | GenerateNoiseRequest::Billow { sampling, .. }
            | GenerateNoiseRequest::RidgedMulti { sampling, .. }
            | GenerateNoiseRequest::HybridMulti { sampling, .. }
            | GenerateNoiseRequest::PingPong { sampling, .. }
            | GenerateNoiseRequest::DomainWarp { sampling, .. }
            | GenerateNoiseRequest::Combinator { sampling, .. }
            | GenerateNoiseRequest::Utility { sampling, .. }
            | GenerateNoiseRequest::White { sampling, .. } => sampling.size.clone(),
        }
    }

    fn should_normalize(&self) -> bool {
        match self {
            GenerateNoiseRequest::Perlin { output, .. }
            | GenerateNoiseRequest::Simplex { output, .. }
            | GenerateNoiseRequest::OpenSimplex2 { output, .. }
            | GenerateNoiseRequest::SuperSimplex { output, .. }
            | GenerateNoiseRequest::Value { output, .. }
            | GenerateNoiseRequest::Cellular { output, .. }
            | GenerateNoiseRequest::Fbm { output, .. }
            | GenerateNoiseRequest::Billow { output, .. }
            | GenerateNoiseRequest::RidgedMulti { output, .. }
            | GenerateNoiseRequest::HybridMulti { output, .. }
            | GenerateNoiseRequest::PingPong { output, .. }
            | GenerateNoiseRequest::DomainWarp { output, .. }
            | GenerateNoiseRequest::Combinator { output, .. }
            | GenerateNoiseRequest::Utility { output, .. }
            | GenerateNoiseRequest::White { output, .. } => {
                output.as_ref().map(|o| o.normalize).unwrap_or(false)
            }
        }
    }
}

// ─── Noise generation per algorithm ──────────────────────────────────────────

fn generate_field(field: &mut Vec<Vec<f64>>, payload: &GenerateNoiseRequest, size: &[usize]) {
    let width = size[0];
    let height = size[1];

    match payload {
        GenerateNoiseRequest::Perlin { params, .. } => {
            let seed = get_seed(params.seed) as i32;
            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
            fill_2d_fnl(field, width, height, &noise);
        }
        GenerateNoiseRequest::Simplex { params, .. } => {
            let seed = get_seed(params.seed);
            let simplex = Simplex::new(seed);
            fill_2d_noise_rs(field, width, height, &simplex);
        }
        GenerateNoiseRequest::OpenSimplex2 { params, .. } => {
            let seed = get_seed(params.seed) as i32;
            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::OpenSimplex2));
            fill_2d_fnl(field, width, height, &noise);
        }
        GenerateNoiseRequest::SuperSimplex { params, .. } => {
            let seed = get_seed(params.seed);
            let supersimplex = SuperSimplex::new(seed);
            fill_2d_noise_rs(field, width, height, &supersimplex);
        }
        GenerateNoiseRequest::Value { params, .. } => {
            let seed = get_seed(params.seed) as i32;
            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Value));
            fill_2d_fnl(field, width, height, &noise);
        }
        GenerateNoiseRequest::Cellular { params, .. } => {
            let seed = get_seed(params.seed) as i32;
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
            fill_2d_fnl(field, width, height, &noise);
        }
        GenerateNoiseRequest::Fbm { params, .. } => {
            let seed = get_seed(params.seed);
            let octaves = params.octaves.unwrap_or(4);
            let frequency = params.frequency.unwrap_or(0.1);
            let lacunarity = params.lacunarity.unwrap_or(2.0);
            let persistence = params.persistence.unwrap_or(0.5);
            let fbm = noise::Fbm::<Perlin>::new(seed)
                .set_octaves(octaves)
                .set_frequency(frequency)
                .set_lacunarity(lacunarity)
                .set_persistence(persistence);
            fill_2d_noise_rs(field, width, height, &fbm);
        }
        GenerateNoiseRequest::Billow { params, .. } => {
            let seed = get_seed(params.seed);
            let octaves = params.octaves.unwrap_or(4);
            let frequency = params.frequency.unwrap_or(0.1);
            let lacunarity = params.lacunarity.unwrap_or(2.0);
            let persistence = params.persistence.unwrap_or(0.5);
            let billow = noise::Billow::<Perlin>::new(seed)
                .set_octaves(octaves)
                .set_frequency(frequency)
                .set_lacunarity(lacunarity)
                .set_persistence(persistence);
            fill_2d_noise_rs(field, width, height, &billow);
        }
        GenerateNoiseRequest::RidgedMulti { params, .. } => {
            let seed = get_seed(params.seed);
            let octaves = params.octaves.unwrap_or(4);
            let frequency = params.frequency.unwrap_or(0.1);
            let lacunarity = params.lacunarity.unwrap_or(2.0);
            let persistence = params.persistence.unwrap_or(1.0);
            let ridged = noise::RidgedMulti::<Perlin>::new(seed)
                .set_octaves(octaves)
                .set_frequency(frequency)
                .set_lacunarity(lacunarity)
                .set_persistence(persistence);
            fill_2d_noise_rs(field, width, height, &ridged);
        }
        GenerateNoiseRequest::HybridMulti { params, .. } => {
            let seed = get_seed(params.seed);
            let octaves = params.octaves.unwrap_or(4);
            let frequency = params.frequency.unwrap_or(0.1);
            let lacunarity = params.lacunarity.unwrap_or(2.0);
            let persistence = params.persistence.unwrap_or(0.25);
            let hybrid = HybridMulti::<Perlin>::new(seed)
                .set_octaves(octaves)
                .set_frequency(frequency)
                .set_lacunarity(lacunarity)
                .set_persistence(persistence);
            fill_2d_noise_rs(field, width, height, &hybrid);
        }
        GenerateNoiseRequest::PingPong { params, .. } => {
            let seed = get_seed(params.seed) as i32;
            let strength = params.strength.unwrap_or(2.0);
            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_fractal_type(Some(fastnoise_lite::FractalType::PingPong));
            noise.set_fractal_ping_pong_strength(Some(strength as f32));
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
            fill_2d_fnl(field, width, height, &noise);
        }
        GenerateNoiseRequest::DomainWarp { params, .. } => {
            let seed = get_seed(params.seed) as i32;
            let amplitude = params.amplitude.unwrap_or(1.0);
            let mut noise = FastNoiseLite::with_seed(seed);
            noise.set_domain_warp_type(Some(fastnoise_lite::DomainWarpType::OpenSimplex2));
            noise.set_domain_warp_amp(Some(amplitude as f32));
            for y in 0..height {
                for x in 0..width {
                    let (warped_x, warped_y) = noise.domain_warp_2d(x as f32, y as f32);
                    let mut base_noise = FastNoiseLite::with_seed(seed + 1);
                    base_noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
                    field[y][x] = base_noise.get_noise_2d(warped_x, warped_y) as f64;
                }
            }
        }
        GenerateNoiseRequest::Combinator { params, .. } => {
            let seed = get_seed(params.seed);
            let op = params.op.as_ref().unwrap_or(&CombinatorOp::Add);
            let source1 = Perlin::new(seed);
            let source2 = Perlin::new(seed + 1);
            for y in 0..height {
                for x in 0..width {
                    let pos = [x as f64 * 0.1, y as f64 * 0.1];
                    field[y][x] = match op {
                        CombinatorOp::Add => Add::new(source1, source2).get(pos),
                        CombinatorOp::Multiply => Multiply::new(source1, source2).get(pos),
                        CombinatorOp::Min => Min::new(source1, source2).get(pos),
                        CombinatorOp::Max => Max::new(source1, source2).get(pos),
                        CombinatorOp::Blend => {
                            let blend_factor = params.blend_factor.unwrap_or(0.5);
                            let control = Constant::new(blend_factor);
                            Blend::new(source1, source2, control).get(pos)
                        }
                    };
                }
            }
        }
        GenerateNoiseRequest::Utility { params, .. } => {
            let kind = params.kind.as_ref().unwrap_or(&UtilityKind::Constant);
            for y in 0..height {
                for x in 0..width {
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
            let seed = get_seed(params.seed) as u64;
            for y in 0..height {
                for x in 0..width {
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
}

// ─── Shared fill helpers ──────────────────────────────────────────────────────

fn fill_2d_fnl(field: &mut Vec<Vec<f64>>, width: usize, height: usize, noise: &FastNoiseLite) {
    for y in 0..height {
        for x in 0..width {
            field[y][x] = noise.get_noise_2d(x as f32, y as f32) as f64;
        }
    }
}

fn fill_2d_noise_rs(field: &mut Vec<Vec<f64>>, width: usize, height: usize, noise: &impl NoiseFn<f64, 2>) {
    for y in 0..height {
        for x in 0..width {
            field[y][x] = noise.get([x as f64 * 0.1, y as f64 * 0.1]);
        }
    }
}

