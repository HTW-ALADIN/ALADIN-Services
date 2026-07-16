mod cli;
mod lib;

use axum::{
    routing::{get, post},
    Router, response::IntoResponse, Json,
};
use utoipa::OpenApi;
use tokio::net::TcpListener;
use clap::Parser;
use cli::{Cli, Commands, GenerateArgs};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use lib::{AppState, list_algorithms, generate_noise, get_noise_field, get_noise_point};

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    if let Some(command) = cli.command {
        match command {
            Commands::List => {
                handle_list_command().await;
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
                // Continue to server startup with custom host/port
                let bind_addr = format!("{}:{}", host, port);
                println!("Starting server on {}", bind_addr);
                start_server(bind_addr).await;
                return;
            }
        }
    }

    // Default server startup - delegate to start_server function

    // Default server startup
    start_server("0.0.0.0:8000".to_string()).await;
}

async fn start_server(bind_addr: String) {
    let state = AppState {
        fields: Arc::new(Mutex::new(HashMap::new())),
    };

    let app = Router::<AppState>::new()
        .route("/v1/algorithms", get(list_algorithms))
        .route("/v1/noise", post(generate_noise))
        .route("/v1/noise/:id", get(get_noise_field))
        .route("/v1/noise/:id/point", get(get_noise_point))
        .route("/api-docs/openapi.json", get(|| async { 
            Json(lib::ApiDoc::openapi()).into_response() 
        }))
        .with_state(state);

    let listener = TcpListener::bind(&bind_addr).await.unwrap();
    println!("Listening on {}", bind_addr);
    axum::serve(listener, app).await.unwrap();
}

async fn handle_list_command() {
    let algorithms = lib::list_algorithms().await;
    println!("{}", serde_json::to_string_pretty(&algorithms.0).unwrap());
}

async fn handle_generate_command(args: GenerateArgs) {
    use lib::{GenerateNoiseRequest, Sampling, AppState};
    
    // Build parameters map
    let mut params = std::collections::HashMap::new();
    params.insert("seed".to_string(), Value::Number(serde_json::Number::from(args.seed)));
    
    for (key, value) in args.params {
        params.insert(key, value);
    }
    
    // Create sampling configuration
    let sampling = Sampling {
        mode: "2d".to_string(),
        dimensions: 2,
        size: Some(vec![args.width, args.height]),
    };
    
    // Build request based on algorithm
    let request = match args.algorithm.as_str() {
        "perlin" => GenerateNoiseRequest::Perlin {
            backend: args.backend,
            params: Value::Object(params.into_iter().collect()),
            sampling,
            output: None,
        },
        "simplex" => GenerateNoiseRequest::Simplex {
            backend: args.backend,
            params: Value::Object(params.into_iter().collect()),
            sampling,
            output: None,
        },
        "white" => GenerateNoiseRequest::White {
            params: Value::Object(params.into_iter().collect()),
            sampling,
            output: None,
        },
        // Add more algorithms as needed
        _ => {
            eprintln!("Unsupported algorithm: {}", args.algorithm);
            eprintln!("Run 'noise-generation-service list' to see available algorithms");
            std::process::exit(1);
        }
    };
    
    // Create temporary state for generation
    let state = AppState {
        fields: Arc::new(Mutex::new(HashMap::new())),
    };
    
    // Generate noise
    let (status, result) = lib::generate_noise(
        axum::extract::State(state.clone()),
        axum::Json(request)
    ).await;
    
    match args.format.as_str() {
        "json" => {
            let output = serde_json::json!({
                "status": status.as_u16(),
                "result": result.0
            });
            
            if let Some(file) = args.output {
                std::fs::write(file, serde_json::to_string_pretty(&output).unwrap()).unwrap();
            } else {
                println!("{}", serde_json::to_string_pretty(&output).unwrap());
            }
        }
        "csv" => {
            // Get the generated field from state
            let fields = state.fields.lock().unwrap();
            if let Some(field) = fields.get(&result.0.id) {
                let mut csv_output = String::new();
                for row in field {
                    csv_output.push_str(&row.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(","));
                    csv_output.push('\n');
                }
                
                if let Some(file) = args.output {
                    std::fs::write(file, csv_output).unwrap();
                } else {
                    print!("{}", csv_output);
                }
            }
        }
        _ => {
            eprintln!("Unsupported output format: {}", args.format);
            std::process::exit(1);
        }
    }
}

async fn handle_openapi_command(format: String, output: Option<String>) {
    let spec = lib::ApiDoc::openapi();
    
    let output_str = match format.as_str() {
        "json" => serde_json::to_string_pretty(&spec).unwrap(),
        "yaml" => {
            eprintln!("YAML output not yet implemented");
            std::process::exit(1);
        }
        _ => {
            eprintln!("Unsupported format: {}", format);
            std::process::exit(1);
        }
    };
    
    if let Some(file) = output {
        std::fs::write(file, output_str).unwrap();
    } else {
        println!("{}", output_str);
    }
}