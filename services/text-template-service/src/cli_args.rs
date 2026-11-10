use std::path::PathBuf;

use clap::{Args, Parser, Subcommand, ValueEnum};

#[derive(Debug, Parser)]
#[command(name = "text-template-service")]
#[command(about = "Render MiniJinja text templates through a local CLI or REST server")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    /// Start the REST API.
    Server {
        #[arg(long, default_value = "0.0.0.0")]
        host: String,
        #[arg(long, default_value_t = 8000)]
        port: u16,
    },
    /// Render a template locally through the same core used by the REST API.
    Render(RenderArgs),
    /// Write the generated OpenAPI document.
    Openapi {
        #[arg(long, value_enum, default_value_t = OpenapiFormat::Yaml)]
        format: OpenapiFormat,
        #[arg(long)]
        output: Option<PathBuf>,
    },
}

#[derive(Debug, Args)]
pub struct RenderArgs {
    /// Template file, or '-' to read the template from stdin.
    #[arg(
        long,
        required_unless_present = "template_dir",
        conflicts_with = "template_dir"
    )]
    pub template: Option<PathBuf>,
    /// Directory containing an in-memory template bundle.
    #[arg(
        long,
        required_unless_present = "template",
        conflicts_with = "template"
    )]
    pub template_dir: Option<PathBuf>,
    /// Bundle entrypoint, relative to --template-dir.
    #[arg(long, requires = "template_dir")]
    pub entrypoint: Option<String>,
    /// JSON context file, or '-' to read context from stdin.
    #[arg(long)]
    pub context: PathBuf,
    #[arg(long, value_enum, default_value_t = CliUndefined::Strict)]
    pub undefined: CliUndefined,
    #[arg(long, value_enum, default_value_t = CliAutoescape::None)]
    pub autoescape: CliAutoescape,
    /// Strip one trailing newline using MiniJinja's standard behavior.
    #[arg(long)]
    pub strip_trailing_newline: bool,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum CliUndefined {
    Strict,
    Lenient,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum CliAutoescape {
    None,
    Html,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum OpenapiFormat {
    Json,
    Yaml,
}
