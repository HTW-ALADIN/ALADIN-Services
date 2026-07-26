use clap::Parser;
use noise_generation_service::cli::{Cli, Commands, Format, OpenApiFormat};
use noise_generation_service::limits::DEFAULT_SAMPLING_SIZE;

#[test]
fn test_cli_parse_generate() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "perlin"]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.algorithm, "perlin");
            assert_eq!(args.output_format, Format::Json);
            // The `--sampling-size` clap default is a hand-written string
            // literal (clap attribute macros can't reference a `const`
            // array directly); pin it against the single source of truth
            // (`crate::limits::DEFAULT_SAMPLING_SIZE`, also used by
            // `service::generate`'s HTTP-path default) so the two can't
            // silently drift apart.
            assert_eq!(args.sampling_size, DEFAULT_SAMPLING_SIZE.to_vec());
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_generate_rejects_unknown_algorithm() {
    let result = Cli::try_parse_from(["test", "generate", "--algorithm", "not-a-real-algorithm"]);
    assert!(result.is_err());
}

#[test]
fn test_cli_generate_custom_size() {
    let cli = Cli::parse_from([
        "test",
        "generate",
        "--algorithm",
        "fbm",
        "--sampling-size",
        "128,256",
    ]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.algorithm, "fbm");
            assert_eq!(args.sampling_size, vec![128, 256]);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_generate_json_params() {
    let cli = Cli::parse_from([
        "test",
        "generate",
        "--algorithm",
        "cellular",
        "--params",
        r#"{"seed": 42, "jitter": 0.5}"#,
    ]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.algorithm, "cellular");
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
            assert_eq!(format, Format::Json);
        }
        _ => panic!("Expected List command"),
    }
}

#[test]
fn test_cli_list_format_csv() {
    let cli = Cli::parse_from(["test", "list", "--format", "csv"]);
    match cli.command {
        Some(Commands::List { format }) => {
            assert_eq!(format, Format::Csv);
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
    let cli = Cli::parse_from([
        "test",
        "generate",
        "--algorithm",
        "simplex",
        "--output-format",
        "csv",
    ]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.output_format, Format::Csv);
            assert!(!args.output_normalize);
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_generate_normalize() {
    let cli = Cli::parse_from([
        "test",
        "generate",
        "--algorithm",
        "perlin",
        "--output-normalize",
    ]);
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
