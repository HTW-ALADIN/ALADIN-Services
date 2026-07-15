use clap::{Parser, Subcommand};

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