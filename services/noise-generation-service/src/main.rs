use axum::{routing::post, Router};
use noise::{NoiseFn, Perlin}; // Beispiel für noise-rs

#[tokio::main]
async fn main() {
    // Initialisierung von noise-rs
    let perlin = Perlin::new(1);
    let val = perlin.get([0.5, 0.5, 0.0]);
    println!("noise-rs value: {}", val);

    // Router für die API
    let app = Router::new().route("/v1/noise", post(generate_noise));

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    println!("Listening on port 3000");
    axum::serve(listener, app).await.unwrap();
}

async fn generate_noise() -> &'static str {
    "Noise generation endpoint"
}
