use clap::{Args, Parser, Subcommand, ValueEnum};
use serde_json::Value;
use std::path::PathBuf;
use std::fmt;

// ─── Algorithm Enum ───────────────────────────────────────────────────────────

#[derive(ValueEnum, Clone, Debug, PartialEq)]
pub enum Algorithm {
    Perlin,
    Simplex,
    OpenSimplex2,
    SuperSimplex,
    Value,
    Cellular,
    Fbm,
    Billow,
    RidgedMulti,
    HybridMulti,
    PingPong,
    DomainWarp,
    Combinator,
    Utility,
    White,
}

impl fmt::Display for Algorithm {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Algorithm::Perlin => write!(f, "perlin"),
            Algorithm::Simplex => write!(f, "simplex"),
            Algorithm::OpenSimplex2 => write!(f, "opensimplex2"),
            Algorithm::SuperSimplex => write!(f, "supersimplex"),
            Algorithm::Value => write!(f, "value"),
            Algorithm::Cellular => write!(f, "cellular"),
            Algorithm::Fbm => write!(f, "fbm"),
            Algorithm::Billow => write!(f, "billow"),
            Algorithm::RidgedMulti => write!(f, "ridged_multi"),
            Algorithm::HybridMulti => write!(f, "hybrid_multi"),
            Algorithm::PingPong => write!(f, "pingpong"),
            Algorithm::DomainWarp => write!(f, "domain_warp"),
            Algorithm::Combinator => write!(f, "combinator"),
            Algorithm::Utility => write!(f, "utility"),
            Algorithm::White => write!(f, "white"),
        }
    }
}

// ─── Format Enums ─────────────────────────────────────────────────────────────

#[derive(ValueEnum, Clone, Debug, PartialEq)]
pub enum ListFormat {
    Json,
    Csv,
}

impl fmt::Display for ListFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ListFormat::Json => write!(f, "json"),
            ListFormat::Csv => write!(f, "csv"),
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

#[derive(ValueEnum, Clone, Debug, PartialEq)]
pub enum GenerateFormat {
    Json,
    Csv,
}

impl fmt::Display for GenerateFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GenerateFormat::Json => write!(f, "json"),
            GenerateFormat::Csv => write!(f, "csv"),
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
        format: ListFormat,
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
    /// Algorithm to use
    #[arg(short, long)]
    pub algorithm: Algorithm,

    /// Size of noise field (comma-separated, e.g. "64,64" or "64" for square)
    #[arg(short, long, default_value = "64,64", value_delimiter = ',', num_args = 1..=4)]
    pub size: Vec<usize>,

    /// Output format: json (default) or csv
    #[arg(short, long, default_value = "json")]
    pub format: GenerateFormat,

    /// Output file (stdout if not specified)
    #[arg(short, long)]
    pub output: Option<PathBuf>,

    /// Algorithm parameters as JSON object (e.g. '{"seed": 42}')
    #[arg(long, default_value = "{}", value_parser = parse_params_json)]
    pub params: serde_json::Value,

    /// Normalize output values to [0,1] range
    #[arg(long)]
    pub normalize: bool,
}

