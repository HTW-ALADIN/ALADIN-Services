#![allow(special_module_name)]

mod cli;
mod lib;

use axum::{
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use clap::{CommandFactory, Parser};
use cli::{Algorithm, Cli, Commands, GenerateArgs, GenerateFormat, ListFormat, OpenApiFormat};
use std::path::PathBuf;
use tokio::net::TcpListener;
use utoipa::OpenApi;

use lib::{generate_noise, list_algorithms};

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    if let Some(command) = cli.command {
        match command {
            Commands::List { format } => {
                handle_list_command(format).await;
                return;
            }
            Commands::Generate(args) => {
                handle_generate_command(args).await;
                return;
            }
            Commands::OpenApi { format, output } => {
                handle_openapi_command(format, output).await;
                return;
            }
            Commands::Server { port, host } => {
                let bind_addr = format!("{}:{}", host, port);
                println!("Starting server on {}", bind_addr);
                start_server(bind_addr).await;
                return;
            }
        }
    }

    // No subcommand — show help
    Cli::command().print_help().unwrap();
    println!();
    std::process::exit(1);
}

// ─── Server ──────────────────────────────────────────────────────────────────

async fn start_server(bind_addr: String) {
    let app = Router::new()
        .route("/v1/algorithms", get(list_algorithms))
        .route("/v1/noise", post(generate_noise))
        .route(
            "/api-docs/openapi.json",
            get(|| async { Json(lib::ApiDoc::openapi()).into_response() }),
        );

    let listener = TcpListener::bind(&bind_addr).await.unwrap();
    println!("Listening on {}", bind_addr);
    axum::serve(listener, app).await.unwrap();
}

// ─── CLI: list ───────────────────────────────────────────────────────────────

async fn handle_list_command(format: ListFormat) {
    let algorithms = lib::list_algorithms().await;
    let data: Vec<serde_json::Value> = algorithms
        .0
        .into_iter()
        .map(|a| serde_json::to_value(a).unwrap())
        .collect();
    match format {
        ListFormat::Csv => {
            // CSV: flat output — algorithm name column, defaults as compact JSON
            println!("algorithm,defaults");
            for entry in &data {
                let name = entry["name"].as_str().unwrap_or("");
                let defaults = entry["defaults"].to_string().replace('"', "\"\"");
                println!("\"{}\",\"{}\"", name, defaults);
            }
            println!("\nTotal: {} algorithms", data.len());
        }
        ListFormat::Json => {
            println!("{}", serde_json::to_string_pretty(&data).unwrap());
        }
    }
}

// ─── CLI: generate (local) ───────────────────────────────────────────────────

fn build_sampling(size: Vec<usize>) -> lib::Sampling {
    lib::Sampling {
        size: Some(size),
    }
}

fn parse_typed_params<T>(params: serde_json::Value) -> T
where
    T: serde::de::DeserializeOwned + Default,
{
    if params.is_null() || params.as_object().is_some_and(|o| o.is_empty()) {
        return T::default();
    }
    match serde_json::from_value(params) {
        Ok(parsed) => parsed,
        Err(err) => {
            eprintln!("Error: invalid params object ({})", err);
            std::process::exit(1);
        }
    }
}

async fn handle_generate_command(args: GenerateArgs) {
    use lib::GenerateNoiseRequest;

    let size = args.sampling_size.clone();
    let sampling = build_sampling(args.sampling_size);

    // `lib::generate_noise` always produces a JSON body (CSV rendering below is
    // done locally from that JSON), so always request JSON here regardless of
    // `--output-format`; `generate_noise` rejects `output.format: csv` requests
    // since the HTTP API itself has no CSV response support.
    let output = Some(lib::Output {
        format: lib::OutputFormat::Json,
        normalize: args.output_normalize,
    });

    // Build the algorithm params — single match, no duplicated output/sampling
    let algorithm = match args.algorithm {
        Algorithm::Perlin => lib::AlgorithmParams::Perlin(parse_typed_params::<lib::SeedParams>(args.params)),
        Algorithm::Simplex => lib::AlgorithmParams::Simplex(parse_typed_params::<lib::SeedParams>(args.params)),
        Algorithm::OpenSimplex2 => lib::AlgorithmParams::OpenSimplex2(parse_typed_params::<lib::SeedParams>(args.params)),
        Algorithm::SuperSimplex => lib::AlgorithmParams::SuperSimplex(parse_typed_params::<lib::SeedParams>(args.params)),
        Algorithm::Value => lib::AlgorithmParams::Value(parse_typed_params::<lib::SeedParams>(args.params)),
        Algorithm::Cellular => lib::AlgorithmParams::Cellular(parse_typed_params::<lib::CellularParams>(args.params)),
        Algorithm::Fbm => lib::AlgorithmParams::Fbm(parse_typed_params::<lib::FractalParams>(args.params)),
        Algorithm::Billow => lib::AlgorithmParams::Billow(parse_typed_params::<lib::FractalParams>(args.params)),
        Algorithm::RidgedMulti => lib::AlgorithmParams::RidgedMulti(parse_typed_params::<lib::RidgedMultiParams>(args.params)),
        Algorithm::HybridMulti => lib::AlgorithmParams::HybridMulti(parse_typed_params::<lib::RidgedMultiParams>(args.params)),
        Algorithm::PingPong => lib::AlgorithmParams::PingPong(parse_typed_params::<lib::PingPongParams>(args.params)),
        Algorithm::DomainWarp => lib::AlgorithmParams::DomainWarp(parse_typed_params::<lib::DomainWarpParams>(args.params)),
        Algorithm::Combinator => lib::AlgorithmParams::Combinator(parse_typed_params::<lib::CombinatorParams>(args.params)),
        Algorithm::Utility => lib::AlgorithmParams::Utility(parse_typed_params::<lib::UtilityParams>(args.params)),
        Algorithm::White => lib::AlgorithmParams::White(parse_typed_params::<lib::SeedParams>(args.params)),
    };

    let request = GenerateNoiseRequest { algorithm, sampling, output };

    // Generate noise
    let (status, result) = lib::generate_noise(axum::Json(request)).await;

    // Surface generation errors instead of silently exiting 0 with empty/partial
    // output — `result.0.status` carries the human-readable error message.
    if !status.is_success() {
        eprintln!("Error: {}", result.0.status);
        std::process::exit(1);
    }

    // Output
    match args.output_format {
        GenerateFormat::Json => {
            let output = serde_json::json!({
                "status": status.as_u16(),
                "result": result.0
            });
            let text = serde_json::to_string_pretty(&output).unwrap();
            write_or_print(text, args.output_file);
        }
        GenerateFormat::Csv => {
            let dim = size.len();
            if dim > 2 {
                eprintln!("Error: CSV output only supports 1D/2D noise fields; use --output-format json for {dim}D data");
                std::process::exit(1);
            }
            let mut csv = String::new();
            // data is serde_json::Value: for 2D it's an array of arrays; for 1D it's a flat array
            if let Some(rows) = result.0.data.as_array() {
                for row in rows {
                    if let Some(values) = row.as_array() {
                        csv.push_str(
                            &values
                                .iter()
                                .map(|v| {
                                    format!("{:.6}", v.as_f64().unwrap_or(0.0))
                                })
                                .collect::<Vec<_>>()
                                .join(","),
                        );
                        csv.push('\n');
                    } else {
                        // 1D: treat as single row
                        csv.push_str(&format!("{:.6}\n", row.as_f64().unwrap_or(0.0)));
                    }
                }
            }
            write_or_print(csv, args.output_file);
        }
    }
}

// ─── CLI: openapi ────────────────────────────────────────────────────────────

async fn handle_openapi_command(format: OpenApiFormat, output: Option<PathBuf>) {
    use utoipa::OpenApi;
    let spec = lib::ApiDoc::openapi();

    let text = match format {
        OpenApiFormat::Json => serde_json::to_string_pretty(&spec).unwrap(),
        OpenApiFormat::Yaml => {
            let json_val: serde_json::Value =
                serde_json::from_str(&serde_json::to_string_pretty(&spec).unwrap()).unwrap();
            serde_yaml::to_string(&json_val).unwrap()
        }
    };

    write_or_print(text, output);
}

// ─── Helper: write to file or stdout ─────────────────────────────────────────

fn write_or_print(text: String, file: Option<PathBuf>) {
    if let Some(path) = file {
        std::fs::write(&path, &text).unwrap_or_else(|e| {
            eprintln!("Error: could not write to {} ({})", path.display(), e);
            std::process::exit(1);
        });
    } else {
        println!("{}", text);
    }
}
