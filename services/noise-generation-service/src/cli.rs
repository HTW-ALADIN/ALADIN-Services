//! `clap` CLI argument definitions.
//!
//! The `--algorithm` flag previously had its own parallel `Algorithm` enum
//! (with a hand-written `Display` impl re-encoding each variant back to the
//! exact wire-name string `crate::algorithms::AlgorithmParams` already
//! defines via `#[serde(rename = ...)]`) plus a 15-arm bridge match in
//! `main.rs` to convert between the two enums. Both algorithm identity lists
//! had to be kept in sync by hand.
//!
//! Now `--algorithm` is validated at parse time against
//! `crate::algorithms::ALGORITHM_NAMES` (the same table the HTTP API and
//! `GET /v1/algorithms` use) and stored as the wire-name `String` directly,
//! so `main.rs` can hand it straight to `serde_json` to build an
//! `AlgorithmParams` value — no second enum, no bridge match.

use clap::{Args, Parser, Subcommand, ValueEnum};
use serde_json::Value;
use std::fmt;
use std::path::PathBuf;

use crate::algorithms::ALGORITHM_NAMES;

/// Parses and validates an `--algorithm` value against `ALGORITHM_NAMES`,
/// producing a clap-friendly error listing the valid options on failure.
///
/// Also accepts the previous CLI spelling of multi-word algorithm names.
/// Before this module existed, `--algorithm` was a `clap::ValueEnum` that
/// (with no `#[value(name = ...)]` overrides) exposed clap's default
/// kebab-case value names — e.g. `ridged-multi`, `open-simplex2`,
/// `ping-pong` — which differ from the wire-format snake_case names used
/// everywhere else (`ridged_multi`, `opensimplex2`, `pingpong`). Matching
/// against the input with hyphens both converted to underscores *and*
/// stripped entirely covers every previously-valid spelling
/// (`ridged-multi` -> `ridged_multi`, `ping-pong` -> `pingpong`,
/// `open-simplex2` -> `opensimplex2`) without hardcoding a per-name alias
/// table.
fn parse_algorithm(s: &str) -> Result<String, String> {
    let underscored = s.replace('-', "_");
    let collapsed = s.replace('-', "");
    if let Some(name) = ALGORITHM_NAMES
        .iter()
        .find(|n| **n == s || **n == underscored || **n == collapsed)
    {
        Ok(name.to_string())
    } else {
        Err(format!(
            "invalid algorithm '{s}' (expected one of: {})",
            ALGORITHM_NAMES.join(", ")
        ))
    }
}

// ─── Format Enums ─────────────────────────────────────────────────────────────

/// Output format shared by the `list` and `generate` CLI commands. This is a
/// CLI-only rendering choice — unrelated to `model::OutputFormat`, which
/// describes the HTTP API's (JSON-only) response format.
#[derive(ValueEnum, Clone, Debug, PartialEq)]
pub enum Format {
    Json,
    Csv,
}

impl fmt::Display for Format {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Format::Json => write!(f, "json"),
            Format::Csv => write!(f, "csv"),
        }
    }
}

#[derive(ValueEnum, Clone, Debug, PartialEq)]
pub enum OpenApiFormat {
    Json,
    Yaml,
}

impl fmt::Display for OpenApiFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            OpenApiFormat::Json => write!(f, "json"),
            OpenApiFormat::Yaml => write!(f, "yaml"),
        }
    }
}

// ─── Custom Parsers ───────────────────────────────────────────────────────────

fn parse_params_json(s: &str) -> Result<Value, String> {
    serde_json::from_str(s).map_err(|e| format!("invalid JSON params: {}", e))
}

// ─── CLI Structure ────────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(author, version, about, long_about = None)]
#[command(name = "noise-generation-service")]
#[command(about = "Unified CLI for noise generation algorithms")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand, Debug, PartialEq)]
pub enum Commands {
    /// List all available algorithms
    #[command(alias = "ls")]
    List {
        /// Output format: json (default) or csv
        #[arg(short, long, default_value = "json")]
        format: Format,
    },

    /// Generate noise using specified algorithm (local)
    #[command(alias = "gen")]
    Generate(GenerateArgs),

    /// Start the HTTP server
    #[command(alias = "serve")]
    Server {
        /// Port to listen on
        #[arg(short, long, default_value = "8000")]
        port: u16,

        /// Host to bind to
        #[arg(long, default_value = "0.0.0.0")]
        host: String,
    },

    /// Generate OpenAPI specification
    #[command(name = "openapi")]
    OpenApi {
        /// Output format (json, yaml)
        #[arg(short, long, default_value = "json")]
        format: OpenApiFormat,

        /// Output file (stdout if not specified)
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
}

#[derive(Args, Debug, PartialEq, Clone)]
pub struct GenerateArgs {
    /// Algorithm to use (see `list` for the full set of valid names)
    #[arg(short, long, value_parser = parse_algorithm)]
    pub algorithm: String,

    /// Size of noise field (comma-separated, e.g. "64,64" or "64" for square).
    /// Maps to `sampling.size` in the API.
    ///
    /// `default_value` must be a string literal (clap's attribute macro
    /// can't reference `crate::limits::DEFAULT_SAMPLING_SIZE` directly), so
    /// this is pinned against that constant by
    /// `tests/cli_tests.rs::test_cli_parse_generate` instead — update both
    /// if the default ever changes.
    #[arg(
        short = 's', long = "sampling-size",
        default_value = "64,64", value_delimiter = ',', num_args = 1..=4,
        visible_alias = "size"
    )]
    pub sampling_size: Vec<usize>,

    /// Output format: json (default) or csv. Maps to `output.format` in the API.
    #[arg(
        short = 'f',
        long = "output-format",
        default_value = "json",
        visible_alias = "format"
    )]
    pub output_format: Format,

    /// Output file (stdout if not specified). CLI-only, not part of the API schema.
    #[arg(short = 'o', long = "output-file", visible_alias = "output")]
    pub output_file: Option<PathBuf>,

    /// Algorithm parameters as JSON object (e.g. '{"seed": 42}')
    #[arg(long, default_value = "{}", value_parser = parse_params_json)]
    pub params: serde_json::Value,

    /// Normalize output values to [0,1] range. Maps to `output.normalize` in the API.
    #[arg(long = "output-normalize", visible_alias = "normalize")]
    pub output_normalize: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_unknown_algorithm_name() {
        assert!(parse_algorithm("not-a-real-algorithm").is_err());
    }

    #[test]
    fn accepts_every_known_algorithm_name() {
        for name in ALGORITHM_NAMES {
            assert_eq!(parse_algorithm(name), Ok(name.to_string()));
        }
    }

    /// Regression test: `--algorithm` used to be a `clap::ValueEnum` with no
    /// `#[value(name = ...)]` overrides, which exposed clap's default
    /// kebab-case value names for multi-word variants. These must keep
    /// working so existing scripts/CLI invocations don't silently break.
    #[test]
    fn accepts_legacy_kebab_case_aliases() {
        let cases = [
            ("open-simplex2", "opensimplex2"),
            ("super-simplex", "supersimplex"),
            ("ridged-multi", "ridged_multi"),
            ("hybrid-multi", "hybrid_multi"),
            ("ping-pong", "pingpong"),
            ("domain-warp", "domain_warp"),
        ];
        for (legacy, canonical) in cases {
            assert_eq!(
                parse_algorithm(legacy),
                Ok(canonical.to_string()),
                "legacy alias '{legacy}' should map to '{canonical}'"
            );
        }
    }
}
