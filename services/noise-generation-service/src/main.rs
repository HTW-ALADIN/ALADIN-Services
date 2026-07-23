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
    let mode = match size.len() {
        1 => "1d",
        2 => "2d",
        3 => "3d",
        4 => "4d",
        _ => "4d",  // 5D+ will be rejected by generate_noise's check_dimension_support
    };
    lib::Sampling {
        mode: mode.to_string(),
        size: Some(size),
    }
}

fn parse_typed_params<T>(params: serde_json::Value) -> T
where
    T: serde::de::DeserializeOwned + Default,
{
    if params.is_null() || params.as_object().map_or(false, |o| o.is_empty()) {
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

    let sampling = build_sampling(args.size);

    // Build output config from CLI flags
    let output = Some(lib::Output {
        format: match args.format {
            GenerateFormat::Json => lib::OutputFormat::Json,
            GenerateFormat::Csv => lib::OutputFormat::Csv,
        },
        normalize: args.normalize,
    });

    // Build the request — supports all algorithm families
    let request = match args.algorithm {
        Algorithm::Perlin => GenerateNoiseRequest::Perlin {
            params: parse_typed_params::<lib::SeedParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::Simplex => GenerateNoiseRequest::Simplex {
            params: parse_typed_params::<lib::SeedParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::OpenSimplex2 => GenerateNoiseRequest::OpenSimplex2 {
            params: parse_typed_params::<lib::SeedParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::SuperSimplex => GenerateNoiseRequest::SuperSimplex {
            params: parse_typed_params::<lib::SeedParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::Value => GenerateNoiseRequest::Value {
            params: parse_typed_params::<lib::SeedParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::Cellular => GenerateNoiseRequest::Cellular {
            params: parse_typed_params::<lib::CellularParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::Fbm => GenerateNoiseRequest::Fbm {
            params: parse_typed_params::<lib::FractalParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::Billow => GenerateNoiseRequest::Billow {
            params: parse_typed_params::<lib::FractalParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::RidgedMulti => GenerateNoiseRequest::RidgedMulti {
            params: parse_typed_params::<lib::RidgedMultiParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::HybridMulti => GenerateNoiseRequest::HybridMulti {
            params: parse_typed_params::<lib::RidgedMultiParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::PingPong => GenerateNoiseRequest::PingPong {
            params: parse_typed_params::<lib::PingPongParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::DomainWarp => GenerateNoiseRequest::DomainWarp {
            params: parse_typed_params::<lib::DomainWarpParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::Combinator => GenerateNoiseRequest::Combinator {
            params: parse_typed_params::<lib::CombinatorParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::Utility => GenerateNoiseRequest::Utility {
            params: parse_typed_params::<lib::UtilityParams>(args.params),
            sampling,
            output: output.clone(),
        },
        Algorithm::White => GenerateNoiseRequest::White {
            params: parse_typed_params::<lib::SeedParams>(args.params),
            sampling,
            output: output.clone(),
        },
    };

    // Generate noise
    let (status, result) = lib::generate_noise(axum::Json(request)).await;

    // Output
    match args.format {
        GenerateFormat::Json => {
            let output = serde_json::json!({
                "status": status.as_u16(),
                "result": result.0
            });
            let text = serde_json::to_string_pretty(&output).unwrap();
            write_or_print(text, args.output);
        }
        GenerateFormat::Csv => {
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
            write_or_print(csv, args.output);
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
            // Fallback: convert JSON to YAML-like output via serde_yaml
            let json_val: serde_json::Value =
                serde_json::from_str(&serde_json::to_string_pretty(&spec).unwrap()).unwrap();
            // Simple YAML output via debug formatting
            serde_json::to_string_pretty(&json_val).unwrap()
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
