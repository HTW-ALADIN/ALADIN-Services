//! Request-size limits shared by validation in `crate::service`.

/// Maximum extent allowed for any single sampling dimension. Bounds per-request
/// memory/CPU cost and prevents pathological requests from exhausting the host.
pub const MAX_SAMPLING_DIM: usize = 4096;

/// Maximum total number of cells (product of all dimensions) allowed per
/// request. Chosen to keep the largest response well under typical memory
/// limits (16M f64 cells ~ 128 MB flat buffer before JSON shaping).
pub const MAX_SAMPLING_CELLS: usize = 16 * 1024 * 1024;

/// Default grid size used when a request omits `sampling.size`. Large enough
/// to show visible noise structures, small enough to keep response payload
/// manageable (~32 KB for f64 values). Matches common examples in noise
/// library documentation.
pub const DEFAULT_SAMPLING_SIZE: [usize; 2] = [64, 64];
