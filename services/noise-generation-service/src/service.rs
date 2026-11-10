//! HTTP-free core generation service.
//!
//! [`generate`] is the shared core both the CLI and the `POST /v1/noise`
//! handler (`crate::http`) call into: it validates the request and runs the
//! CPU-bound generation, and returns a plain `Result` with no HTTP
//! dependency.

use crate::dim::Dim;
use crate::error::NoiseError;
use crate::generate::generate_flat;
use crate::limits::{DEFAULT_SAMPLING_SIZE, MAX_SAMPLING_CELLS, MAX_SAMPLING_DIM};
use crate::model::GenerateNoiseRequest;
use crate::resolve::resolve_params;
use crate::shape::shape_data;

/// A successfully generated noise field, independent of how it will be
/// rendered (HTTP JSON body, CLI JSON, or CLI CSV).
#[derive(Debug)]
pub struct GeneratedField {
    pub data: serde_json::Value,
    pub size: Vec<usize>,
    pub params_used: serde_json::Value,
}

/// Validates `request` and — if valid — runs the (CPU-bound) noise
/// generation and shapes the result. Callers that care about not blocking
/// an async executor (the HTTP handler) should run this inside
/// `tokio::task::spawn_blocking`; the CLI calls it directly since it has no
/// other concurrent work to protect.
pub fn generate(request: &GenerateNoiseRequest) -> Result<GeneratedField, NoiseError> {
    let size = request
        .sampling_size()
        .unwrap_or_else(|| DEFAULT_SAMPLING_SIZE.to_vec());

    let dim =
        Dim::from_len(size.len()).ok_or(NoiseError::UnsupportedSizeLength { len: size.len() })?;

    if request.wants_unsupported_csv() {
        return Err(NoiseError::UnsupportedCsv);
    }

    let support = request.algorithm.dim_support();
    if !support.supports(dim) {
        return Err(NoiseError::UnsupportedDimension {
            algorithm: request.algorithm.name(),
            dim,
            reason: support.reason(),
        });
    }

    // Reject pathological grid sizes before allocating anything. Each
    // dimension is capped individually and the total cell count is computed
    // with checked arithmetic so a huge or overflowing request can't reach
    // `vec![0.0; total]`.
    if size.iter().any(|&d| d == 0 || d > MAX_SAMPLING_DIM) {
        return Err(NoiseError::DimensionOutOfRange {
            size,
            max: MAX_SAMPLING_DIM,
        });
    }
    let total = match size.iter().try_fold(1usize, |acc, &d| acc.checked_mul(d)) {
        Some(total) if total <= MAX_SAMPLING_CELLS => total,
        _ => {
            return Err(NoiseError::TooManyCells {
                size,
                max: MAX_SAMPLING_CELLS,
            })
        }
    };

    // Resolve parameters once — used for both generation and the response echo.
    let resolved = resolve_params(request);
    let normalize = request.should_normalize();

    let mut flat = vec![0.0; total];
    generate_flat(&mut flat, request, &resolved, &size, dim);

    if normalize {
        normalize_in_place(&mut flat);
    }

    let data = shape_data(&flat, &size, dim);
    Ok(GeneratedField {
        data,
        size,
        params_used: resolved.to_json(),
    })
}

fn normalize_in_place(flat: &mut [f64]) {
    let mut min_val = f64::MAX;
    let mut max_val = f64::MIN;
    for &v in flat.iter() {
        if v < min_val {
            min_val = v;
        }
        if v > max_val {
            max_val = v;
        }
    }
    let range = max_val - min_val;
    if range > 0.0 {
        for v in flat.iter_mut() {
            *v = (*v - min_val) / range;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::algorithms::AlgorithmParams;
    use crate::model::{Output, OutputFormat, Sampling, SeedParams};

    fn request(size: Vec<usize>) -> GenerateNoiseRequest {
        GenerateNoiseRequest {
            algorithm: AlgorithmParams::Perlin(SeedParams { seed: Some(1) }),
            sampling: Sampling { size: Some(size) },
            output: Some(Output {
                format: OutputFormat::Json,
                normalize: false,
            }),
        }
    }

    #[test]
    fn normalize_in_place_scales_to_unit_range() {
        let mut flat = vec![-2.0, 0.0, 2.0, 4.0];
        normalize_in_place(&mut flat);
        assert_eq!(flat, vec![0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0]);
    }

    #[test]
    fn normalize_in_place_is_noop_for_constant_input() {
        let mut flat = vec![5.0, 5.0, 5.0];
        normalize_in_place(&mut flat);
        assert_eq!(flat, vec![5.0, 5.0, 5.0]);
    }

    #[test]
    fn rejects_zero_dimension() {
        let req = request(vec![0, 4]);
        assert_eq!(
            generate(&req).unwrap_err(),
            NoiseError::DimensionOutOfRange {
                size: vec![0, 4],
                max: MAX_SAMPLING_DIM
            }
        );
    }

    #[test]
    fn rejects_unsupported_size_length() {
        let req = request(vec![1, 2, 3, 4, 5]);
        assert_eq!(
            generate(&req).unwrap_err(),
            NoiseError::UnsupportedSizeLength { len: 5 }
        );
    }

    #[test]
    fn succeeds_for_valid_2d_request() {
        let req = request(vec![4, 4]);
        let field = generate(&req).unwrap();
        assert_eq!(field.size, vec![4, 4]);
        assert_eq!(field.params_used["seed"], 1);
        assert_eq!(field.data.as_array().unwrap().len(), 4);
    }
}
