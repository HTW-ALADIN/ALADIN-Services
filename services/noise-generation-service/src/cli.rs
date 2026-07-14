use clap::{Parser, Subcommand};

#[derive(Parser)]
#[clap(name = "noise-gen", about = "Noise Generation CLI")]
pub struct Cli {
    #[clap(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand)]
pub enum Commands {
    Generate {
        #[clap(short, long)]
        algorithm: String,
        #[clap(short, long)]
        backend: Option<String>,
    },
}
