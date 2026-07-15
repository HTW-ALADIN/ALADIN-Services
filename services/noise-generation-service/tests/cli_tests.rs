use clap::Parser;
use noise_generation_service::cli::{Cli, Commands};

#[test]
fn test_cli_parse_generate() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "perlin"]);
    match cli.command {
        Some(Commands::Generate { algorithm, backend }) => {
            assert_eq!(algorithm, "perlin");
            assert_eq!(backend, None);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_parse_generate_with_backend() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "simplex", "--backend", "fastnoise_lite"]);
    match cli.command {
        Some(Commands::Generate { algorithm, backend }) => {
            assert_eq!(algorithm, "simplex");
            assert_eq!(backend, Some("fastnoise_lite".to_string()));
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_no_command() {
    let cli = Cli::parse_from(["test"]);
    assert_eq!(cli.command, None);
}