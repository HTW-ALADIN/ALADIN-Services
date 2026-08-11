use std::{
    collections::BTreeMap,
    fs,
    io::{self, Read, Write},
    path::{Path, PathBuf},
};

use clap::{Args, Parser, Subcommand, ValueEnum};
use serde_json::{Map, Value};
use utoipa::OpenApi;

use crate::{
    config::Limits,
    error::ServiceError,
    model::{Autoescape, RenderOptions, RenderRequest, TemplateSource, UndefinedBehavior},
    openapi::ApiDoc,
    renderer,
};

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

pub fn execute_render(args: RenderArgs, limits: &Limits) -> Result<String, ServiceError> {
    if args.template.as_deref() == Some(Path::new("-")) && args.context == Path::new("-") {
        return Err(ServiceError::invalid(
            "template and context cannot both be read from stdin",
        ));
    }

    let context_text = read_text(&args.context, "context")?;
    let context: Map<String, Value> = serde_json::from_str::<Value>(&context_text)
        .map_err(|error| ServiceError::invalid(format!("context is not valid JSON: {error}")))?
        .as_object()
        .cloned()
        .ok_or_else(|| ServiceError::invalid("context must be a JSON object"))?;

    let source = if let Some(template_path) = args.template {
        TemplateSource::Inline {
            template: read_text(&template_path, "template")?,
            name: template_path
                .file_name()
                .and_then(|name| name.to_str())
                .filter(|_| template_path != Path::new("-"))
                .map(ToOwned::to_owned),
        }
    } else {
        let directory = args
            .template_dir
            .ok_or_else(|| ServiceError::invalid("--template-dir is required"))?;
        let entrypoint = args
            .entrypoint
            .ok_or_else(|| ServiceError::invalid("--entrypoint is required for a bundle"))?;
        TemplateSource::Bundle {
            entrypoint,
            templates: load_bundle(&directory)?,
        }
    };

    let request = RenderRequest {
        source,
        context,
        options: RenderOptions {
            undefined: match args.undefined {
                CliUndefined::Strict => UndefinedBehavior::Strict,
                CliUndefined::Lenient => UndefinedBehavior::Lenient,
            },
            autoescape: match args.autoescape {
                CliAutoescape::None => Autoescape::None,
                CliAutoescape::Html => Autoescape::Html,
            },
            keep_trailing_newline: !args.strip_trailing_newline,
        },
    };
    renderer::render(&request, limits).map(|response| response.output)
}

pub fn write_openapi(
    format: OpenapiFormat,
    output: Option<&Path>,
) -> Result<(), Box<dyn std::error::Error>> {
    let document = ApiDoc::openapi();
    let text = match format {
        OpenapiFormat::Json => serde_json::to_string_pretty(&document)?,
        OpenapiFormat::Yaml => serde_yaml::to_string(&document)?,
    };
    if let Some(path) = output {
        fs::write(path, text)?;
    } else {
        print!("{text}");
    }
    Ok(())
}

pub fn write_problem(error: &ServiceError) {
    let text = serde_json::to_string(&error.problem())
        .unwrap_or_else(|_| "{\"title\":\"Internal CLI error\"}".to_string());
    let _ = writeln!(io::stderr(), "{text}");
}

fn read_text(path: &Path, kind: &str) -> Result<String, ServiceError> {
    if path == Path::new("-") {
        let mut text = String::new();
        io::stdin()
            .read_to_string(&mut text)
            .map_err(|error| ServiceError::invalid(format!("could not read {kind}: {error}")))?;
        return Ok(text);
    }
    fs::read_to_string(path).map_err(|error| {
        ServiceError::invalid(format!("could not read {kind} {}: {error}", path.display()))
    })
}

fn load_bundle(root: &Path) -> Result<BTreeMap<String, String>, ServiceError> {
    let root = root.canonicalize().map_err(|error| {
        ServiceError::invalid(format!(
            "could not open template directory {}: {error}",
            root.display()
        ))
    })?;
    if !root.is_dir() {
        return Err(ServiceError::invalid("--template-dir must be a directory"));
    }
    let mut templates = BTreeMap::new();
    collect_bundle_files(&root, &root, &mut templates)?;
    Ok(templates)
}

fn collect_bundle_files(
    root: &Path,
    directory: &Path,
    templates: &mut BTreeMap<String, String>,
) -> Result<(), ServiceError> {
    let entries = fs::read_dir(directory).map_err(|error| {
        ServiceError::invalid(format!(
            "could not read template directory {}: {error}",
            directory.display()
        ))
    })?;
    for entry in entries {
        let entry = entry.map_err(|error| {
            ServiceError::invalid(format!("could not read template directory entry: {error}"))
        })?;
        let file_type = entry.file_type().map_err(|error| {
            ServiceError::invalid(format!(
                "could not inspect {}: {error}",
                entry.path().display()
            ))
        })?;
        if file_type.is_symlink() {
            return Err(ServiceError::invalid(format!(
                "symlinks are not allowed in template bundles: {}",
                entry.path().display()
            )));
        }
        if file_type.is_dir() {
            collect_bundle_files(root, &entry.path(), templates)?;
        } else if file_type.is_file() {
            let path = entry.path();
            let relative = path.strip_prefix(root).map_err(|_| {
                ServiceError::invalid("template path escaped the selected directory")
            })?;
            let logical_name = relative
                .components()
                .map(|component| component.as_os_str().to_string_lossy())
                .collect::<Vec<_>>()
                .join("/");
            let source = fs::read_to_string(&path).map_err(|error| {
                ServiceError::invalid(format!(
                    "template {} is not readable UTF-8: {error}",
                    path.display()
                ))
            })?;
            templates.insert(logical_name, source);
        }
    }
    Ok(())
}
