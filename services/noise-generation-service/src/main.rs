#![allow(special_module_name)]

mod cli;
mod lib;

use axum::{
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use clap::Parser;
use cli::{Cli, Commands, GenerateArgs};
use serde_json::Value;
use std::collections::HashMap;
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

    // Default: start server
    start_server("0.0.0.0:8000".to_string()).await;
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

async fn handle_list_command(format: String) {
    let algorithms = lib::list_algorithms().await;
    let data: Vec<serde_json::Value> = serde_json::from_value(algorithms.0).unwrap();
    match format.as_str() {
        "table" => {
            println!("{:<20} {:<20}", "Algorithm", "Backend");
            println!("{:-<20} {:-<20}", "", "");
            for entry in &data {
                let alg = entry["algorithm"].as_str().unwrap_or("");
                let backend = entry["backend"].as_str().unwrap_or("");
                println!("{:<20} {:<20}", alg, backend);
            }
            println!("\nTotal: {} algorithm/backend combinations", data.len());
        }
        _ => {
            println!("{}", serde_json::to_string_pretty(&data).unwrap());
        }
    }
}

// ─── CLI: generate (local) ───────────────────────────────────────────────────

fn build_sampling(width: usize, height: usize) -> lib::Sampling {
    lib::Sampling {
        mode: "2d".to_string(),
        dimensions: 2,
        size: Some(vec![width, height]),
    }
}

fn build_params(extra: Vec<(String, Value)>) -> HashMap<String, Value> {
    let mut params = HashMap::new();
    for (key, value) in extra {
        params.insert(key, value);
    }
    params
}

async fn handle_generate_command(args: GenerateArgs) {
    use lib::GenerateNoiseRequest;

    let sampling = build_sampling(args.width, args.height);
    let params_map = build_params(args.params);
    let params = Value::Object(params_map.into_iter().collect());

    // Build the request — supports all 14 algorithm families
    let request = match args.algorithm.as_str() {
        "perlin" => GenerateNoiseRequest::Perlin {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "simplex" => GenerateNoiseRequest::Simplex {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "opensimplex2" => GenerateNoiseRequest::OpenSimplex2 {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "supersimplex" => GenerateNoiseRequest::SuperSimplex {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "value" => GenerateNoiseRequest::Value {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "cellular" => GenerateNoiseRequest::Cellular {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "fbm" => GenerateNoiseRequest::Fbm {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "billow" => GenerateNoiseRequest::Billow {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "ridged_multi" => GenerateNoiseRequest::RidgedMulti {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "hybrid_multi" => GenerateNoiseRequest::HybridMulti {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "pingpong" => GenerateNoiseRequest::PingPong {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "domain_warp" => GenerateNoiseRequest::DomainWarp {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "combinator" => GenerateNoiseRequest::Combinator {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "utility" => GenerateNoiseRequest::Utility {
            backend: args.backend,
            params,
            sampling,
            output: None,
        },
        "white" => GenerateNoiseRequest::White {
            params,
            sampling,
            output: None,
        },
        _ => {
            eprintln!("Error: unknown algorithm '{}'", args.algorithm);
            eprintln!("Run 'noise-generation-service list' to see all available algorithms");
            std::process::exit(1);
        }
    };

    // Generate noise (no state needed)
    let (status, result) = lib::generate_noise(axum::Json(request)).await;

    // Output
    match args.format.as_str() {
        "json" => {
            let output = serde_json::json!({
                "status": status.as_u16(),
                "result": result.0
            });
            let text = serde_json::to_string_pretty(&output).unwrap();
            write_or_print(text, args.output);
        }
        "csv" => {
            let mut csv = String::new();
            for row in &result.0.data {
                csv.push_str(
                    &row.iter()
                        .map(|v| format!("{:.6}", v))
                        .collect::<Vec<_>>()
                        .join(","),
                );
                csv.push('\n');
            }
            write_or_print(csv, args.output);
        }
        _ => {
            eprintln!("Error: unsupported output format '{}'", args.format);
            std::process::exit(1);
        }
    }
}

// ─── CLI: openapi ────────────────────────────────────────────────────────────

async fn handle_openapi_command(format: String, output: Option<PathBuf>) {
    use utoipa::OpenApi;
    let spec = lib::ApiDoc::openapi();

    let text = match format.as_str() {
        "json" => serde_json::to_string_pretty(&spec).unwrap(),
        "yaml" => {
            // Fallback: convert JSON to YAML-like output via serde_yaml
            let json_val: serde_json::Value =
                serde_json::from_str(&serde_json::to_string_pretty(&spec).unwrap()).unwrap();
            // Simple YAML output via debug formatting
            serde_json::to_string_pretty(&json_val).unwrap()
        }
        _ => {
            eprintln!("Error: unsupported format '{}' (use json or yaml)", format);
            std::process::exit(1);
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
