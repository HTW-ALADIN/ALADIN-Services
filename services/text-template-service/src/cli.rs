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
    let entries =
        fs::read_dir(directory).map_err(|error| directory_read_error(directory, error))?;
    for entry in entries {
        let entry = entry.map_err(directory_entry_error)?;
        let file_type = entry
            .file_type()
            .map_err(|error| inspect_path_error(&entry.path(), error))?;
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
            let relative = path.strip_prefix(root).map_err(|_| escaped_path_error())?;
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

fn directory_read_error(directory: &Path, error: io::Error) -> ServiceError {
    ServiceError::invalid(format!(
        "could not read template directory {}: {error}",
        directory.display()
    ))
}

fn directory_entry_error(error: io::Error) -> ServiceError {
    ServiceError::invalid(format!("could not read template directory entry: {error}"))
}

fn inspect_path_error(path: &Path, error: io::Error) -> ServiceError {
    ServiceError::invalid(format!("could not inspect {}: {error}", path.display()))
}

fn escaped_path_error() -> ServiceError {
    ServiceError::invalid("template path escaped the selected directory")
}

#[cfg(test)]
mod tests {
    use std::{fs, io};

    use super::{
        directory_entry_error, directory_read_error, escaped_path_error, execute_render,
        inspect_path_error, load_bundle, read_text, CliAutoescape, CliUndefined, RenderArgs,
    };
    use crate::config::Limits;

    fn render_args(context: &std::path::Path) -> RenderArgs {
        RenderArgs {
            template: None,
            template_dir: None,
            entrypoint: None,
            context: context.to_path_buf(),
            undefined: CliUndefined::Strict,
            autoescape: CliAutoescape::None,
            strip_trailing_newline: false,
        }
    }

    #[test]
    fn reports_missing_files_and_directories() {
        let directory = tempfile::tempdir().unwrap();
        let missing = directory.path().join("missing");

        assert!(read_text(&missing, "template")
            .unwrap_err()
            .detail
            .contains("could not read template"));
        assert!(load_bundle(&missing)
            .unwrap_err()
            .detail
            .contains("could not open template directory"));
    }

    #[test]
    fn rejects_a_file_as_the_bundle_root() {
        let directory = tempfile::tempdir().unwrap();
        let file = directory.path().join("template.txt");
        fs::write(&file, "template").unwrap();

        assert_eq!(
            load_bundle(&file).unwrap_err().detail,
            "--template-dir must be a directory"
        );
    }

    #[test]
    fn execute_render_requires_a_template_source_and_bundle_entrypoint() {
        let directory = tempfile::tempdir().unwrap();
        let context = directory.path().join("context.json");
        fs::write(&context, "{}").unwrap();

        let missing_source = execute_render(render_args(&context), &Limits::default()).unwrap_err();
        assert_eq!(missing_source.detail, "--template-dir is required");

        let mut missing_entrypoint = render_args(&context);
        missing_entrypoint.template_dir = Some(directory.path().to_path_buf());
        let error = execute_render(missing_entrypoint, &Limits::default()).unwrap_err();
        assert_eq!(error.detail, "--entrypoint is required for a bundle");
    }

    #[test]
    fn rejects_non_utf8_bundle_files() {
        let directory = tempfile::tempdir().unwrap();
        fs::write(directory.path().join("invalid.txt"), [0xff]).unwrap();

        assert!(load_bundle(directory.path())
            .unwrap_err()
            .detail
            .contains("is not readable UTF-8"));
    }

    #[test]
    fn formats_low_level_bundle_io_errors() {
        let error = || io::Error::other("failure");
        assert!(
            directory_read_error(std::path::Path::new("templates"), error())
                .detail
                .contains("could not read template directory templates")
        );
        assert!(directory_entry_error(error())
            .detail
            .contains("could not read template directory entry"));
        assert!(
            inspect_path_error(std::path::Path::new("template.txt"), error())
                .detail
                .contains("could not inspect template.txt")
        );
        assert_eq!(
            escaped_path_error().detail,
            "template path escaped the selected directory"
        );
    }

    #[cfg(unix)]
    #[test]
    fn ignores_non_file_directory_entries() {
        use std::os::unix::net::UnixListener;

        let directory = tempfile::tempdir().unwrap();
        let _socket = UnixListener::bind(directory.path().join("service.sock")).unwrap();

        assert!(load_bundle(directory.path()).unwrap().is_empty());
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlinks_in_bundle_directories() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().unwrap();
        let target = directory.path().join("target.txt");
        fs::write(&target, "target").unwrap();
        symlink(&target, directory.path().join("link.txt")).unwrap();

        assert!(load_bundle(directory.path())
            .unwrap_err()
            .detail
            .contains("symlinks are not allowed"));
    }
}
