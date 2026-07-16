use clap::{Parser, Subcommand, Args};
use serde_json::Value;
use std::collections::HashMap;

#[derive(Parser)]
#[command(author, version, about, long_about = None)]
#[command(name = "noise-generation-service")]
#[command(about = "Unified CLI for noise generation algorithms")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand)]
pub enum Commands {
    /// List all available algorithms and backends
    #[command(alias = "ls")]
    List,
    
    /// Generate noise using specified algorithm
    #[command(alias = "gen")]
    Generate(GenerateArgs),
    
    /// Start the HTTP server
    #[command(alias = "serve")]
    Server {
        /// Port to listen on
        #[arg(short, long, default_value = "8000")]
        port: u16,
        
        /// Host to bind to
        #[arg(long, default_value = "0.0.0.0")]
        host: String,
    },
    
    /// Generate OpenAPI specification
    #[command(name = "openapi")]
    OpenApi {
        /// Output format (json, yaml)
        #[arg(short, long, default_value = "json")]
        format: String,
        
        /// Output file (stdout if not specified)
        #[arg(short, long)]
        output: Option<String>,
    },
}

#[derive(Args)]
pub struct GenerateArgs {
    /// Algorithm to use
    #[arg(short, long)]
    pub algorithm: String,
    
    /// Backend to use (if applicable)
    #[arg(short, long)]
    pub backend: Option<String>,
    
    /// Seed value for reproducible noise
    #[arg(short, long, default_value = "42")]
    pub seed: u64,
    
    /// Width of noise field
    #[arg(short, long, default_value = "64")]
    pub width: usize,
    
    /// Height of noise field  
    #[arg(long, default_value = "64")]
    pub height: usize,
    
    /// Output format (json, csv, png)
    #[arg(short, long, default_value = "json")]
    pub format: String,
    
    /// Output file (stdout if not specified)
    #[arg(short, long)]
    pub output: Option<String>,
    
    /// Additional algorithm parameters (key=value pairs)
    #[arg(long = "param", value_parser = parse_key_val)]
    pub params: Vec<(String, Value)>,
    
    /// Normalize output values to [0,1] range
    #[arg(long)]
    pub normalize: bool,
}

fn parse_key_val(s: &str) -> Result<(String, Value), Box<dyn std::error::Error + Send + Sync + 'static>> {
    let pos = s.find('=')
        .ok_or_else(|| format!("invalid KEY=value: no `=` found in `{}`", s))?;
    
    let key = s[..pos].to_string();
    let value_str = &s[pos + 1..];
    
    // Try to parse as different types
    let value = if let Ok(num) = value_str.parse::<i64>() {
        Value::Number(serde_json::Number::from(num))
    } else if let Ok(num) = value_str.parse::<f64>() {
        Value::Number(serde_json::Number::from_f64(num).unwrap_or(serde_json::Number::from(0)))
    } else if let Ok(b) = value_str.parse::<bool>() {
        Value::Bool(b)
    } else {
        Value::String(value_str.to_string())
    };
    
    Ok((key, value))
}

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand, Debug, PartialEq)]
pub enum Commands {
    /// Generate noise with specified algorithm and backend
    Generate {
        /// The noise algorithm to use
        #[arg(long)]
        algorithm: String,
        
        /// The backend implementation to use
        #[arg(long)]
        backend: Option<String>,
    },
}