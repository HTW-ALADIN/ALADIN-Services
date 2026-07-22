use clap::Parser;
#[path = "../src/cli.rs"]
mod cli;
use cli::{Cli, Commands};

#[test]
fn test_cli_parse_generate() {
    let cli = Cli::parse_from(["test", "generate", "--algorithm", "perlin"]);
    match cli.command {
        Some(Commands::Generate(args)) => {
            assert_eq!(args.algorithm, "perlin");
        }
        _ => panic!("Expected Generate command"),
    }
}

#[test]
fn test_cli_no_command() {
    let cli = Cli::parse_from(["test"]);
    assert_eq!(cli.command, None);
}
