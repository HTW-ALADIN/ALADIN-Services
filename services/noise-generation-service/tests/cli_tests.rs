use clap::Parser;
#[path = "../src/cli.rs"]
mod cli;
use cli::{Algorithm, Cli, Commands, GenerateFormat, ListFormat, OpenApiFormat};

#[test]
fn test_cli_parse_generate() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "perlin"]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.algorithm, Algorithm::Perlin);
            assert_eq!(args.output_format, GenerateFormat::Json);
            assert_eq!(args.sampling_size, vec![64, 64]);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_generate_custom_size() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "fbm", "--sampling-size", "128,256"]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.algorithm, Algorithm::Fbm);
            assert_eq!(args.sampling_size, vec![128, 256]);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_generate_json_params() {
    let cli = Cli::parse_from([
        "test", "generate", "--algorithm", "cellular",
        "--params", r#"{"seed": 42, "jitter": 0.5}"#,
    ]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.algorithm, Algorithm::Cellular);
            assert_eq!(args.params["seed"], 42);
            assert_eq!(args.params["jitter"], 0.5);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_list_format_json() {
    let cli = Cli::parse_from(["test", "list"]);
    match cli.command {
        Some(Commands::List { format }) => {
            assert_eq!(format, ListFormat::Json);
        }
        _ => panic!("Expected List command"),
    }
}

#[test]
fn test_cli_list_format_csv() {
    let cli = Cli::parse_from(["test", "list", "--format", "csv"]);
    match cli.command {
        Some(Commands::List { format }) => {
            assert_eq!(format, ListFormat::Csv);
        }
        _ => panic!("Expected List command"),
    }
}

#[test]
fn test_cli_openapi_format_yaml() {
    let cli = Cli::parse_from(["test", "openapi", "--format", "yaml"]);
    match cli.command {
        Some(Commands::OpenApi { format, output }) => {
            assert_eq!(format, OpenApiFormat::Yaml);
            assert_eq!(output, None);
        }
        _ => panic!("Expected OpenApi command"),
    }
}

#[test]
fn test_cli_generate_format_csv() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "simplex", "--output-format", "csv"]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.output_format, GenerateFormat::Csv);
            assert!(!args.output_normalize);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_generate_normalize() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "perlin", "--output-normalize"]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert!(args.output_normalize);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_no_command() {
    let cli = Cli::parse_from(["test"]);
    assert_eq!(cli.command, None);
}
