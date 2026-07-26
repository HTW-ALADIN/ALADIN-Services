use axum::{
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use clap::{CommandFactory, Parser};
use noise_generation_service::algorithms::{algorithm_defaults, AlgorithmParams, ALGORITHM_NAMES};
use noise_generation_service::cli::{Cli, Commands, Format, GenerateArgs, OpenApiFormat};
use noise_generation_service::model::{
    AlgorithmInfo, GenerateNoiseRequest, Output, OutputFormat, Sampling,
};
use noise_generation_service::{generate_noise, list_algorithms, render, service, ApiDoc};
use std::path::PathBuf;
use tokio::net::TcpListener;
use utoipa::OpenApi;

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    let Some(command) = cli.command else {
        // No subcommand — show help
        Cli::command().print_help().unwrap();
        println!();
        std::process::exit(1);
    };

    match command {
        Commands::List { format } => handle_list_command(format),
        Commands::Generate(args) => handle_generate_command(args),
        Commands::OpenApi { format, output } => handle_openapi_command(format, output),
        Commands::Server { port, host } => {
            let bind_addr = format!("{}:{}", host, port);
            println!("Starting server on {}", bind_addr);
            start_server(bind_addr).await;
        }
    }
}

// ─── Server ──────────────────────────────────────────────────────────────────

async fn start_server(bind_addr: String) {
    let app = Router::new()
        .route("/v1/algorithms", get(list_algorithms))
        .route("/v1/noise", post(generate_noise))
        .route(
            "/api-docs/openapi.json",
            get(|| async { Json(ApiDoc::openapi()).into_response() }),
        );

    let listener = match TcpListener::bind(&bind_addr).await {
        Ok(listener) => listener,
        Err(err) => {
            eprintln!("Error: could not bind to {bind_addr} ({err})");
            std::process::exit(1);
        }
    };
    println!("Listening on {}", bind_addr);
    if let Err(err) = axum::serve(listener, app).await {
        eprintln!("Error: server stopped unexpectedly ({err})");
        std::process::exit(1);
    }
}

// ─── CLI: list ───────────────────────────────────────────────────────────────

fn handle_list_command(format: Format) {
    let entries: Vec<AlgorithmInfo> = ALGORITHM_NAMES
        .iter()
        .map(|name| AlgorithmInfo {
            name: name.to_string(),
            defaults: algorithm_defaults(name),
        })
        .collect();

    match format {
        Format::Csv => print!("{}", render::list_csv(&entries)),
        Format::Json => {
            let text = serde_json::to_string_pretty(&entries)
                .unwrap_or_else(|e| unreachable!("AlgorithmInfo always serializes: {e}"));
            println!("{text}");
        }
    }
}

// ─── CLI: generate (local) ───────────────────────────────────────────────────

/// Builds an `AlgorithmParams` value from the CLI's `--algorithm` name and
/// `--params` JSON by round-tripping through the same tag/content
/// deserialization the HTTP API uses — no per-algorithm mapping match needed
/// on the CLI side.
fn build_algorithm(name: &str, params: serde_json::Value) -> AlgorithmParams {
    let params = if params.is_null() || params.as_object().is_some_and(|o| o.is_empty()) {
        serde_json::json!({})
    } else {
        params
    };
    serde_json::from_value(serde_json::json!({ "algorithm": name, "params": params }))
        .unwrap_or_else(|err| {
            eprintln!("Error: invalid params for algorithm '{name}' ({err})");
            std::process::exit(1);
        })
}

fn handle_generate_command(args: GenerateArgs) {
    let size = args.sampling_size.clone();
    let algorithm = build_algorithm(&args.algorithm, args.params);
    let request = GenerateNoiseRequest {
        algorithm,
        sampling: Sampling {
            size: Some(size.clone()),
        },
        output: Some(Output {
            format: OutputFormat::Json,
            normalize: args.output_normalize,
        }),
    };

    let field = match service::generate(&request) {
        Ok(field) => field,
        Err(err) => {
            eprintln!("Error: {}", err.message());
            std::process::exit(1);
        }
    };

    match args.output_format {
        Format::Json => {
            let output = serde_json::json!({
                "status": 201,
                "result": {
                    "id": format!("nsf_{}", uuid::Uuid::new_v4()),
                    "algorithm": args.algorithm,
                    "status": "completed",
                    "data": field.data,
                    "size": field.size,
                    "params_used": field.params_used,
                }
            });
            let text = serde_json::to_string_pretty(&output).unwrap();
            write_or_print(text, args.output_file);
        }
        Format::Csv => match render::generate_csv(&field.data, size.len()) {
            Ok(csv) => write_or_print(csv, args.output_file),
            Err(msg) => {
                eprintln!("Error: {msg}");
                std::process::exit(1);
            }
        },
    }
}

// ─── CLI: openapi ────────────────────────────────────────────────────────────

fn handle_openapi_command(format: OpenApiFormat, output: Option<PathBuf>) {
    let spec = ApiDoc::openapi();

    let text = match format {
        OpenApiFormat::Json => serde_json::to_string_pretty(&spec).unwrap(),
        OpenApiFormat::Yaml => serde_yaml::to_string(&spec).unwrap(),
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
