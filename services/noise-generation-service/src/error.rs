//! Structured errors for noise-field generation.
//!
//! Previously every validation failure in `generate_noise` built its own
//! ad-hoc `NoiseFieldResult` literal by hand (repeated 5x with only the
//! `status` string differing) and returned `StatusCode::BAD_REQUEST`
//! unconditionally. `NoiseError` centralizes the failure cases; the HTTP
//! handler (`crate::http`) is the only place that turns one into the
//! response body, and the CLI can match on it directly instead of parsing
//! a string.

use axum::http::StatusCode;

use crate::dim::Dim;
use crate::model::NoiseFieldResult;

#[derive(Debug, Clone, PartialEq)]
pub enum NoiseError {
    /// `sampling.size` has a length that maps to no supported dimensionality
    /// (0 or 5+ entries).
    UnsupportedSizeLength { len: usize },
    /// The algorithm does not support the requested (but otherwise valid)
    /// dimensionality.
    UnsupportedDimension {
        algorithm: &'static str,
        dim: Dim,
        reason: &'static str,
    },
    /// `output.format: csv` was requested against the HTTP API, which only
    /// ever returns JSON (CSV rendering is CLI-only).
    UnsupportedCsv,
    /// A sampling dimension is zero or exceeds `MAX_SAMPLING_DIM`.
    DimensionOutOfRange { size: Vec<usize>, max: usize },
    /// The total cell count (product of all dimensions) exceeds
    /// `MAX_SAMPLING_CELLS`.
    TooManyCells { size: Vec<usize>, max: usize },
}

impl NoiseError {
    /// All current failure cases map to 400 Bad Request — they are all
    /// client input problems — but centralizing the mapping here means a
    /// future error variant (e.g. an internal generation failure) can pick a
    /// different code without touching every call site.
    pub fn status_code(&self) -> StatusCode {
        StatusCode::BAD_REQUEST
    }

    /// The human-readable description of this error, without the `"error: "`
    /// prefix used in the HTTP response body's `status` field.
    pub fn message(&self) -> String {
        match self {
            NoiseError::UnsupportedSizeLength { len } => {
                format!("sampling.size has {len} dimensions; only 1D-4D are supported")
            }
            NoiseError::UnsupportedDimension {
                algorithm,
                dim,
                reason,
            } => format!("algorithm '{algorithm}' does not support {dim} sampling ({reason})"),
            NoiseError::UnsupportedCsv => {
                "output.format 'csv' is not supported by POST /v1/noise; use the CLI's \
                 --output-format csv, or omit output.format for JSON"
                    .to_string()
            }
            NoiseError::DimensionOutOfRange { size, max } => {
                format!("each sampling dimension must be between 1 and {max} (got {size:?})")
            }
            NoiseError::TooManyCells { size, max } => {
                format!("requested sampling size {size:?} exceeds the maximum of {max} total cells")
            }
        }
    }

    /// Renders this error as the same `NoiseFieldResult` shape historically
    /// returned on failure: `status` is `"error: <message>"`, `data` and
    /// `params_used` are `null`.
    pub fn into_result(self, id: String, algorithm: String, size: Vec<usize>) -> NoiseFieldResult {
        NoiseFieldResult {
            id,
            status: format!("error: {}", self.message()),
            algorithm,
            data: serde_json::Value::Null,
            size,
            params_used: serde_json::Value::Null,
        }
    }
}
