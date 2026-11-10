//! Per-algorithm noise generation into a flat `Vec<f64>` buffer.
//!
//! `size` is the grid extent: `[width]` for 1D, `[width, height]` for 2D,
//! `[width, height, depth]` for 3D, `[width, height, depth, w]` for 4D. Cell
//! iteration order matches `crate::shape::shape_data`, which reshapes the
//! same flat buffer into nested JSON.

use fastnoise_lite::FastNoiseLite;
use noise::{
    Add, Blend, Constant, Cylinders, HybridMulti, Max, Min, MultiFractal, Multiply, NoiseFn,
    Perlin, Seedable, Simplex, SuperSimplex,
};

use crate::algorithms::AlgorithmParams;
use crate::dim::{iter_2d, iter_3d, iter_4d, scaled, Dim};
use crate::model::{
    CellularDistanceFunction, CellularReturnType, CombinatorOp, GenerateNoiseRequest, UtilityKind,
};
use crate::resolve::ResolvedNoiseParams;

/// Evaluates a per-cell closure over every 2D/3D/4D cell, using the shared
/// `crate::dim` iterators for indexing (so the row-major flattening math
/// lives in exactly one place: `crate::dim`). The coordinate-array
/// construction is still repeated once per dimensionality because `noise`'s
/// `NoiseFn` trait is generic over a const array length that Rust cannot
/// infer from a single closure shared across 2/3/4 element arrays — but no
/// nested-loop or index-arithmetic duplication remains here. Shared by
/// Combinator and Utility, which both call into `noise`-crate `NoiseFn`
/// sources with no other algorithm-specific setup.
macro_rules! dispatch_cells {
    ($flat:expr, $size:expr, $dim:expr, |$pos:ident| $body:expr) => {
        match $dim {
            Dim::D2 => {
                for (idx, [x, y]) in iter_2d($size) {
                    let $pos: [f64; 2] = [scaled(x), scaled(y)];
                    $flat[idx] = $body;
                }
            }
            Dim::D3 => {
                for (idx, [x, y, z]) in iter_3d($size) {
                    let $pos: [f64; 3] = [scaled(x), scaled(y), scaled(z)];
                    $flat[idx] = $body;
                }
            }
            Dim::D4 => {
                for (idx, [x, y, z, w]) in iter_4d($size) {
                    let $pos: [f64; 4] = [scaled(x), scaled(y), scaled(z), scaled(w)];
                    $flat[idx] = $body;
                }
            }
            Dim::D1 => {
                unreachable!("dimension already validated: Combinator/Utility require 2D-4D")
            }
        }
    };
}

/// Generates noise into a flat `Vec<f64>` according to the requested
/// dimensionality. `resolved` contains the already-resolved parameters
/// (seed etc.) — this is the *only* place parameter resolution happens for
/// generation, ensuring consistency with `params_used`.
pub fn generate_flat(
    flat: &mut [f64],
    payload: &GenerateNoiseRequest,
    resolved: &ResolvedNoiseParams,
    size: &[usize],
    dim: Dim,
) {
    match (&payload.algorithm, resolved) {
        // ─── fastnoise-lite seed-only algorithms (2D/3D) ───────────────────
        (AlgorithmParams::Perlin(..), ResolvedNoiseParams::SeedOnly { seed }) => {
            fill_fnl_seed_only(flat, size, dim, *seed, fastnoise_lite::NoiseType::Perlin);
        }
        (AlgorithmParams::OpenSimplex2(..), ResolvedNoiseParams::SeedOnly { seed }) => {
            fill_fnl_seed_only(
                flat,
                size,
                dim,
                *seed,
                fastnoise_lite::NoiseType::OpenSimplex2,
            );
        }
        (AlgorithmParams::Value(..), ResolvedNoiseParams::SeedOnly { seed }) => {
            fill_fnl_seed_only(flat, size, dim, *seed, fastnoise_lite::NoiseType::Value);
        }
        (
            AlgorithmParams::Cellular(..),
            ResolvedNoiseParams::Cellular {
                seed,
                distance_function,
                return_type,
                jitter,
            },
        ) => {
            let mut noise = FastNoiseLite::with_seed(*seed as i32);
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Cellular));
            noise.set_cellular_distance_function(Some(distance_function.into()));
            noise.set_cellular_return_type(Some(return_type.into()));
            noise.set_cellular_jitter(Some(*jitter as f32));
            fill_fnl(flat, size, dim, &noise);
        }
        // ─── PingPong: fastnoise-lite fractal ──────────────────────────────
        (AlgorithmParams::PingPong(..), ResolvedNoiseParams::PingPong { seed, strength }) => {
            let mut noise = FastNoiseLite::with_seed(*seed as i32);
            noise.set_fractal_type(Some(fastnoise_lite::FractalType::PingPong));
            noise.set_fractal_ping_pong_strength(Some(*strength as f32));
            noise.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));
            fill_fnl(flat, size, dim, &noise);
        }
        // ─── DomainWarp: fastnoise-lite domain warp ────────────────────────
        (AlgorithmParams::DomainWarp(..), ResolvedNoiseParams::DomainWarp { seed, amplitude }) => {
            fill_domain_warp(flat, size, dim, *seed as i32, *amplitude);
        }
        // ─── noise-crate algorithms (2D/3D/4D) ─────────────────────────────
        (AlgorithmParams::Simplex(..), ResolvedNoiseParams::SeedOnly { seed }) => {
            let simplex = Simplex::new(*seed);
            fill_noise_rs_4d::<Simplex>(flat, size, dim, &simplex);
        }
        (AlgorithmParams::SuperSimplex(..), ResolvedNoiseParams::SeedOnly { seed }) => {
            let s = SuperSimplex::new(*seed);
            fill_noise_rs::<SuperSimplex>(flat, size, dim, &s);
        }
        // ─── Fractal family (Fbm, Billow, RidgedMulti, HybridMulti) ────────
        (
            AlgorithmParams::Fbm(..),
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => fill_fractal::<noise::Fbm<Perlin>>(
            flat,
            size,
            dim,
            *seed,
            *octaves,
            *frequency,
            *lacunarity,
            *persistence,
        ),
        (
            AlgorithmParams::Billow(..),
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => fill_fractal::<noise::Billow<Perlin>>(
            flat,
            size,
            dim,
            *seed,
            *octaves,
            *frequency,
            *lacunarity,
            *persistence,
        ),
        (
            AlgorithmParams::RidgedMulti(..),
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => fill_fractal::<noise::RidgedMulti<Perlin>>(
            flat,
            size,
            dim,
            *seed,
            *octaves,
            *frequency,
            *lacunarity,
            *persistence,
        ),
        (
            AlgorithmParams::HybridMulti(..),
            ResolvedNoiseParams::Fractal {
                seed,
                octaves,
                frequency,
                lacunarity,
                persistence,
            },
        ) => fill_fractal::<HybridMulti<Perlin>>(
            flat,
            size,
            dim,
            *seed,
            *octaves,
            *frequency,
            *lacunarity,
            *persistence,
        ),
        // ─── Combinator ─────────────────────────────────────────────────────
        (
            AlgorithmParams::Combinator(..),
            ResolvedNoiseParams::Combinator {
                seed,
                op,
                blend_factor,
            },
        ) => {
            let source1 = Perlin::new(*seed);
            let source2 = Perlin::new(seed.wrapping_add(1));
            let bf = *blend_factor;
            dispatch_cells!(flat, size, dim, |pos| match op {
                CombinatorOp::Add => Add::new(source1, source2).get(pos),
                CombinatorOp::Multiply => Multiply::new(source1, source2).get(pos),
                CombinatorOp::Min => Min::new(source1, source2).get(pos),
                CombinatorOp::Max => Max::new(source1, source2).get(pos),
                CombinatorOp::Blend => Blend::new(source1, source2, Constant::new(bf)).get(pos),
            });
        }
        // ─── Utility ────────────────────────────────────────────────────────
        (AlgorithmParams::Utility(..), ResolvedNoiseParams::Utility { kind, value }) => {
            let val = *value;
            dispatch_cells!(flat, size, dim, |pos| match kind {
                UtilityKind::Constant => Constant::new(val).get(pos),
                UtilityKind::Cylinders => Cylinders::new().get(pos),
            });
        }
        // ─── White noise ────────────────────────────────────────────────────
        (AlgorithmParams::White(..), ResolvedNoiseParams::SeedOnly { seed }) => {
            fill_white_noise(flat, size, dim, *seed as u64);
        }
        // Safety: payload variant always matches resolved variant — enforced
        // by `resolve_params` producing exactly one `ResolvedNoiseParams`
        // shape per `AlgorithmParams` variant.
        _ => unreachable!("payload/resolved type mismatch — this is a programming error"),
    }
}

impl From<&CellularDistanceFunction> for fastnoise_lite::CellularDistanceFunction {
    fn from(value: &CellularDistanceFunction) -> Self {
        match value {
            CellularDistanceFunction::Euclidean => Self::Euclidean,
            CellularDistanceFunction::EuclideanSq => Self::EuclideanSq,
            CellularDistanceFunction::Manhattan => Self::Manhattan,
            CellularDistanceFunction::Hybrid => Self::Hybrid,
        }
    }
}

impl From<&CellularReturnType> for fastnoise_lite::CellularReturnType {
    fn from(value: &CellularReturnType) -> Self {
        match value {
            CellularReturnType::CellValue => Self::CellValue,
            CellularReturnType::Distance => Self::Distance,
            CellularReturnType::Distance2 => Self::Distance2,
            CellularReturnType::Distance2Add => Self::Distance2Add,
            CellularReturnType::Distance2Sub => Self::Distance2Sub,
            CellularReturnType::Distance2Mul => Self::Distance2Mul,
            CellularReturnType::Distance2Div => Self::Distance2Div,
        }
    }
}

/// Wraps filler for noise-rs fractal types (Fbm, Billow, RidgedMulti, HybridMulti).
#[allow(clippy::too_many_arguments)]
fn fill_fractal<T>(
    flat: &mut [f64],
    size: &[usize],
    dim: Dim,
    seed: u32,
    octaves: usize,
    frequency: f64,
    lacunarity: f64,
    persistence: f64,
) where
    T: NoiseFn<f64, 2> + NoiseFn<f64, 3> + NoiseFn<f64, 4> + MultiFractal + Seedable + Default,
{
    let n = T::default()
        .set_seed(seed)
        .set_octaves(octaves)
        .set_frequency(frequency)
        .set_lacunarity(lacunarity)
        .set_persistence(persistence);
    fill_noise_rs_4d::<T>(flat, size, dim, &n);
}

/// Wraps fill_fnl for seed-only FNL algorithms (Perlin, OpenSimplex2, Value).
fn fill_fnl_seed_only(
    flat: &mut [f64],
    size: &[usize],
    dim: Dim,
    seed: u32,
    noise_type: fastnoise_lite::NoiseType,
) {
    let mut noise = FastNoiseLite::with_seed(seed as i32);
    noise.set_noise_type(Some(noise_type));
    fill_fnl(flat, size, dim, &noise);
}

/// Fills `flat` using fastnoise-lite (2D or 3D only — fastnoise-lite has no
/// 1D or 4D sampling API).
fn fill_fnl(flat: &mut [f64], size: &[usize], dim: Dim, noise: &FastNoiseLite) {
    match dim {
        Dim::D2 => {
            for (idx, [x, y]) in iter_2d(size) {
                flat[idx] = noise.get_noise_2d(x as f32, y as f32) as f64;
            }
        }
        Dim::D3 => {
            for (idx, [x, y, z]) in iter_3d(size) {
                flat[idx] = noise.get_noise_3d(x as f32, y as f32, z as f32) as f64;
            }
        }
        Dim::D1 | Dim::D4 => {
            unreachable!("dimension already validated: fastnoise-lite is 2D/3D only")
        }
    }
}

/// Fills `flat` using a noise-crate `NoiseFn` source (2D or 3D only).
/// Used by `SuperSimplex`, which does not implement `NoiseFn<f64, 4>`.
fn fill_noise_rs<T>(flat: &mut [f64], size: &[usize], dim: Dim, noise: &T)
where
    T: NoiseFn<f64, 2> + NoiseFn<f64, 3>,
{
    match dim {
        Dim::D2 => {
            for (idx, [x, y]) in iter_2d(size) {
                flat[idx] = noise.get([scaled(x), scaled(y)]);
            }
        }
        Dim::D3 => {
            for (idx, [x, y, z]) in iter_3d(size) {
                flat[idx] = noise.get([scaled(x), scaled(y), scaled(z)]);
            }
        }
        Dim::D1 | Dim::D4 => {
            unreachable!("dimension already validated: SuperSimplex is 2D/3D only")
        }
    }
}

/// Fills `flat` using a noise-crate `NoiseFn` source (2D, 3D, or 4D).
/// Used by most noise-rs generators, which implement `NoiseFn` for all three.
fn fill_noise_rs_4d<T>(flat: &mut [f64], size: &[usize], dim: Dim, noise: &T)
where
    T: NoiseFn<f64, 2> + NoiseFn<f64, 3> + NoiseFn<f64, 4>,
{
    match dim {
        Dim::D2 => {
            for (idx, [x, y]) in iter_2d(size) {
                flat[idx] = noise.get([scaled(x), scaled(y)]);
            }
        }
        Dim::D3 => {
            for (idx, [x, y, z]) in iter_3d(size) {
                flat[idx] = noise.get([scaled(x), scaled(y), scaled(z)]);
            }
        }
        Dim::D4 => {
            for (idx, [x, y, z, w]) in iter_4d(size) {
                flat[idx] = noise.get([scaled(x), scaled(y), scaled(z), scaled(w)]);
            }
        }
        Dim::D1 => {
            unreachable!("dimension already validated: noise-crate types require at least 2D")
        }
    }
}

/// Fills `flat` using fastnoise-lite domain warping (2D or 3D only).
fn fill_domain_warp(flat: &mut [f64], size: &[usize], dim: Dim, seed: i32, amplitude: f64) {
    let mut warp = FastNoiseLite::with_seed(seed);
    warp.set_domain_warp_type(Some(fastnoise_lite::DomainWarpType::OpenSimplex2));
    warp.set_domain_warp_amp(Some(amplitude as f32));
    // `base` depends only on `seed`, not on the loop position — build it once
    // outside the loop instead of once per cell.
    let mut base = FastNoiseLite::with_seed(seed.wrapping_add(1));
    base.set_noise_type(Some(fastnoise_lite::NoiseType::Perlin));

    match dim {
        Dim::D2 => {
            for (idx, [x, y]) in iter_2d(size) {
                let (wx, wy) = warp.domain_warp_2d(x as f32, y as f32);
                flat[idx] = base.get_noise_2d(wx, wy) as f64;
            }
        }
        Dim::D3 => {
            for (idx, [x, y, z]) in iter_3d(size) {
                let (wx, wy, wz) = warp.domain_warp_3d(x as f32, y as f32, z as f32);
                flat[idx] = base.get_noise_3d(wx, wy, wz) as f64;
            }
        }
        Dim::D1 | Dim::D4 => unreachable!("dimension already validated: domain warp is 2D/3D only"),
    }
}

// ─── White noise ────────────────────────────────────────────────────────────

/// PCG-style hash constants. `MUL`/`INC` are the standard PCG32 LCG
/// multiplier/increment; `AVALANCHE` and the per-axis mixing constants are
/// arbitrary large odd numbers chosen to decorrelate each coordinate axis
/// before the final hash — their exact values don't matter for correctness,
/// only that they differ per axis and are odd (for good bit mixing).
const PCG_MUL: u64 = 6364136223846793005;
const PCG_INC: u64 = 1442695040888963407;
const AVALANCHE_MUL: u64 = 12741261754838537793;
const AXIS_MUL: [u64; 4] = [374761393, 668265263, 941568331, 1221221227];

/// Uncorrelated per-cell hash noise: each cell's value depends only on the
/// seed and its own integer coordinates, with no interpolation between
/// neighbors (unlike every other algorithm in this service). Supports 1D-4D
/// natively since it has no external-library dimensionality restriction.
fn white_noise(seed: u64, coords: &[usize]) -> f64 {
    let mut state = seed.wrapping_mul(PCG_MUL).wrapping_add(PCG_INC);
    for (axis, &c) in coords.iter().enumerate() {
        state ^= (c as u64).wrapping_mul(AXIS_MUL[axis]);
    }
    state = state.wrapping_mul(AVALANCHE_MUL);
    let hash = state ^ (state >> 31);
    (hash as f64 / u64::MAX as f64) * 2.0 - 1.0
}

fn fill_white_noise(flat: &mut [f64], size: &[usize], dim: Dim, seed: u64) {
    match dim {
        Dim::D1 => {
            for x in 0..size[0] {
                flat[x] = white_noise(seed, &[x]);
            }
        }
        Dim::D2 => {
            for (idx, [x, y]) in iter_2d(size) {
                flat[idx] = white_noise(seed, &[x, y]);
            }
        }
        Dim::D3 => {
            for (idx, [x, y, z]) in iter_3d(size) {
                flat[idx] = white_noise(seed, &[x, y, z]);
            }
        }
        Dim::D4 => {
            for (idx, [x, y, z, w]) in iter_4d(size) {
                flat[idx] = white_noise(seed, &[x, y, z, w]);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn white_noise_is_deterministic_for_same_seed_and_coords() {
        assert_eq!(white_noise(42, &[1, 2]), white_noise(42, &[1, 2]));
    }

    #[test]
    fn white_noise_differs_across_coordinates() {
        assert_ne!(white_noise(42, &[1, 2]), white_noise(42, &[1, 3]));
        assert_ne!(white_noise(42, &[1, 2]), white_noise(42, &[2, 2]));
    }

    #[test]
    fn white_noise_differs_across_seeds() {
        assert_ne!(white_noise(1, &[1, 2]), white_noise(2, &[1, 2]));
    }

    #[test]
    fn white_noise_is_bounded_to_unit_range() {
        for x in 0..50 {
            let v = white_noise(7, &[x, x * 3]);
            assert!((-1.0..=1.0).contains(&v), "value {v} out of range");
        }
    }
}
