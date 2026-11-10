use std::{io::Write, net::SocketAddr, path::Path};

use clap::Parser;
use text_template_service::{
    cli::{self, Cli, Command},
    router, AppState, Limits,
};
use tokio::net::TcpListener;

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    let limits = match Limits::from_env() {
        Ok(limits) => limits,
        Err(error) => {
            eprintln!("configuration error: {error}");
            std::process::exit(2);
        }
    };

    match cli.command {
        Command::Server { host, port } => start_server(host, port, limits).await,
        Command::Render(args) => match cli::execute_render(args, &limits) {
            Ok(output) => {
                if let Err(error) = std::io::stdout().write_all(output.as_bytes()) {
                    eprintln!("could not write rendered output: {error}");
                    std::process::exit(1);
                }
            }
            Err(error) => {
                cli::write_problem(&error);
                std::process::exit(1);
            }
        },
        Command::Openapi { format, output } => {
            if let Err(error) = cli::write_openapi(format, output.as_deref().map(Path::new)) {
                eprintln!("could not write OpenAPI document: {error}");
                std::process::exit(1);
            }
        }
    }
}

async fn start_server(host: String, port: u16, limits: Limits) {
    let address: SocketAddr = match format!("{host}:{port}").parse() {
        Ok(address) => address,
        Err(error) => {
            eprintln!("invalid server address {host}:{port}: {error}");
            std::process::exit(2);
        }
    };
    let listener = match TcpListener::bind(address).await {
        Ok(listener) => listener,
        Err(error) => {
            eprintln!("could not bind to {address}: {error}");
            std::process::exit(1);
        }
    };
    println!("text-template-service listening on {address}");
    if let Err(error) = axum::serve(listener, router(AppState::new(limits))).await {
        eprintln!("server stopped unexpectedly: {error}");
        std::process::exit(1);
    }
}
