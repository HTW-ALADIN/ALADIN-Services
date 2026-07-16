mod cli;
mod lib;

use axum::{
    routing::{get, post},
    Router, response::IntoResponse, Json,
};
use utoipa::OpenApi;
use tokio::net::TcpListener;
use clap::Parser;
use cli::{Cli, Commands};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use utoipa_swagger_ui::SwaggerUi;
use lib::{ApiDoc, AppState, list_algorithms, generate_noise};

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    if let Some(command) = cli.command {
        match command {
            Commands::Generate { algorithm, backend } => {
                println!("Generating noise with algorithm: {}, backend: {:?}", algorithm, backend);
                return;
            }
        }
    }

    let state = AppState {
        fields: Arc::new(Mutex::new(HashMap::new())),
    };

    let app = Router::new()
        .route("/v1/algorithms", get(list_algorithms))
        .route("/v1/noise", post(generate_noise))
        .route("/api-docs/openapi.json", get(|| async { 
            Json(lib::ApiDoc::openapi()).into_response() 
        }))
        .with_state(state);

    let listener = TcpListener::bind("0.0.0.0:8000").await.unwrap();
    println!("Listening on port 8000");
    axum::serve(listener, app).await.unwrap();
}