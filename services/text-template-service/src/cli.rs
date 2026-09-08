use std::{
    collections::BTreeMap,
    fs,
    io::{self, Read, Write},
    path::Path,
};

use serde_json::{Map, Value};
use utoipa::OpenApi;

pub use crate::cli_args::{Cli, CliAutoescape, CliUndefined, Command, OpenapiFormat, RenderArgs};

use crate::{
    config::Limits,
    error::ServiceError,
    model::{Autoescape, RenderOptions, RenderRequest, TemplateSource, UndefinedBehavior},
    openapi::ApiDoc,
    renderer,
};

pub fn execute_render(args: RenderArgs, limits: &Limits) -> Result<String, ServiceError> {
    if args.template.as_deref() == Some(Path::new("-")) && args.context == Path::new("-") {
        return Err(ServiceError::invalid(
            "template and context cannot both be read from stdin",
        ));
    }

    let context_text = read_text(&args.context, "context", limits.max_context_bytes)?;
    let context: Map<String, Value> = serde_json::from_str::<Value>(&context_text)
        .map_err(|error| ServiceError::invalid(format!("context is not valid JSON: {error}")))?
        .as_object()
        .cloned()
        .ok_or_else(|| ServiceError::invalid("context must be a JSON object"))?;

    let source = if let Some(template_path) = args.template {
        TemplateSource::Inline {
            template: read_text(&template_path, "template", limits.max_template_bytes)?,
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
            templates: load_bundle(&directory, limits)?,
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

fn read_text(path: &Path, kind: &str, maximum: usize) -> Result<String, ServiceError> {
    if path == Path::new("-") {
        return read_limited(io::stdin().lock(), kind, maximum);
    }
    let label = format!("{kind} {}", path.display());
    let file = fs::File::open(path)
        .map_err(|error| ServiceError::invalid(format!("could not read {label}: {error}")))?;
    read_limited(file, &label, maximum)
}

fn read_limited(reader: impl Read, label: &str, maximum: usize) -> Result<String, ServiceError> {
    let mut bytes = Vec::with_capacity(maximum.min(8192));
    reader
        .take(maximum.saturating_add(1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|error| ServiceError::invalid(format!("could not read {label}: {error}")))?;
    if bytes.len() > maximum {
        return Err(ServiceError::payload_too_large(format!(
            "{label} exceeds {maximum} bytes"
        )));
    }
    String::from_utf8(bytes)
        .map_err(|error| ServiceError::invalid(format!("{label} is not readable UTF-8: {error}")))
}

fn load_bundle(root: &Path, limits: &Limits) -> Result<BTreeMap<String, String>, ServiceError> {
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
    collect_bundle_files(&root, &mut templates, limits)?;
    Ok(templates)
}

fn collect_bundle_files(
    root: &Path,
    templates: &mut BTreeMap<String, String>,
    limits: &Limits,
) -> Result<(), ServiceError> {
    let mut directories = vec![root.to_path_buf()];
    let maximum_entries = limits
        .max_bundle_templates
        .saturating_mul(2)
        .saturating_add(1);
    let mut entries_seen = 0usize;
    while let Some(directory) = directories.pop() {
        let entries =
            fs::read_dir(&directory).map_err(|error| directory_read_error(&directory, error))?;
        for entry in entries {
            let entry = entry.map_err(directory_entry_error)?;
            entries_seen += 1;
            if entries_seen > maximum_entries {
                return Err(ServiceError::payload_too_large(format!(
                    "bundle traversal exceeds {maximum_entries} entries"
                )));
            }
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
                directories.push(entry.path());
            } else if file_type.is_file() {
                if templates.len() >= limits.max_bundle_templates {
                    return Err(ServiceError::payload_too_large(format!(
                        "bundle contains more than {} templates",
                        limits.max_bundle_templates
                    )));
                }
                let path = entry.path();
                let relative = path.strip_prefix(root).map_err(|_| escaped_path_error())?;
                let logical_name = logical_template_name(relative)?;
                let source = read_text(&path, "template", limits.max_template_bytes)?;
                insert_template(templates, logical_name, source)?;
            }
        }
    }
    Ok(())
}

fn logical_template_name(relative: &Path) -> Result<String, ServiceError> {
    relative
        .components()
        .map(|component| {
            component
                .as_os_str()
                .to_str()
                .ok_or_else(|| ServiceError::invalid("template bundle paths must be valid UTF-8"))
        })
        .collect::<Result<Vec<_>, _>>()
        .map(|components| components.join("/"))
}

fn insert_template(
    templates: &mut BTreeMap<String, String>,
    logical_name: String,
    source: String,
) -> Result<(), ServiceError> {
    if templates.contains_key(&logical_name) {
        return Err(ServiceError::invalid(format!(
            "duplicate template name: {logical_name}"
        )));
    }
    templates.insert(logical_name, source);
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
    use std::{collections::BTreeMap, fs, io};

    use clap::Parser;

    use super::{
        directory_entry_error, directory_read_error, escaped_path_error, execute_render,
        insert_template, inspect_path_error, load_bundle, logical_template_name, read_limited,
        read_text, Cli, CliAutoescape, CliUndefined, RenderArgs,
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
    fn parses_cli_defaults() {
        let server = Cli::try_parse_from(["text-template-service", "server"]).unwrap();
        std::hint::black_box(server);
        let openapi = Cli::try_parse_from(["text-template-service", "openapi"]).unwrap();
        std::hint::black_box(openapi);
        let render = Cli::try_parse_from([
            "text-template-service",
            "render",
            "--template",
            "template.j2",
            "--context",
            "context.json",
        ])
        .unwrap();
        std::hint::black_box(render);
    }

    #[test]
    fn reports_missing_files_and_directories() {
        let directory = tempfile::tempdir().unwrap();
        let missing = directory.path().join("missing");

        assert!(read_text(&missing, "template", 1024)
            .unwrap_err()
            .detail
            .contains("could not read template"));
        assert!(load_bundle(&missing, &Limits::default())
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
            load_bundle(&file, &Limits::default()).unwrap_err().detail,
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

        assert!(load_bundle(directory.path(), &Limits::default())
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

        assert!(load_bundle(directory.path(), &Limits::default())
            .unwrap()
            .is_empty());
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlinks_in_bundle_directories() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().unwrap();
        let target = directory.path().join("target.txt");
        fs::write(&target, "target").unwrap();
        symlink(&target, directory.path().join("link.txt")).unwrap();

        assert!(load_bundle(directory.path(), &Limits::default())
            .unwrap_err()
            .detail
            .contains("symlinks are not allowed"));
    }

    #[test]
    fn bounded_reads_reject_oversized_and_unreadable_inputs() {
        assert_eq!(
            read_limited(&b"too long"[..], "template", 3)
                .unwrap_err()
                .status,
            axum::http::StatusCode::PAYLOAD_TOO_LARGE
        );
        assert!(read_limited(&[0xff][..], "template", 1)
            .unwrap_err()
            .detail
            .contains("not readable UTF-8"));

        struct FailingReader;
        impl io::Read for FailingReader {
            fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
                Err(io::Error::other("failure"))
            }
        }
        assert!(read_limited(FailingReader, "template", 1)
            .unwrap_err()
            .detail
            .contains("could not read template"));
    }

    #[test]
    fn bundle_loading_enforces_file_and_directory_limits() {
        let directory = tempfile::tempdir().unwrap();
        fs::write(directory.path().join("one.txt"), "one").unwrap();
        fs::write(directory.path().join("two.txt"), "two").unwrap();
        let one_template = Limits {
            max_bundle_templates: 1,
            ..Limits::default()
        };
        assert!(load_bundle(directory.path(), &one_template)
            .unwrap_err()
            .detail
            .contains("more than 1 templates"));

        let nested = tempfile::tempdir().unwrap();
        fs::create_dir_all(nested.path().join("a/b/c/d")).unwrap();
        let one_directory = Limits {
            max_bundle_templates: 1,
            ..Limits::default()
        };
        assert!(load_bundle(nested.path(), &one_directory)
            .unwrap_err()
            .detail
            .contains("traversal exceeds 3 entries"));
    }

    #[test]
    fn bundle_name_limits_share_the_renderer_error_contract() {
        let named = tempfile::tempdir().unwrap();
        fs::write(named.path().join("long.txt"), "source").unwrap();
        let context = named.path().join("context.json");
        fs::write(&context, "{}").unwrap();
        let short_names = Limits {
            max_template_name_bytes: 3,
            ..Limits::default()
        };
        let mut args = render_args(&context);
        args.template_dir = Some(named.path().to_path_buf());
        args.entrypoint = Some("long.txt".to_string());

        let error = execute_render(args, &short_names).unwrap_err();

        assert_eq!(error.code, "invalid-request");
        assert!(error.detail.contains("template name exceeds 3 bytes"));
    }

    #[test]
    fn duplicate_logical_names_are_rejected() {
        let mut templates = BTreeMap::new();
        insert_template(&mut templates, "same.txt".into(), "first".into()).unwrap();
        assert!(
            insert_template(&mut templates, "same.txt".into(), "second".into())
                .unwrap_err()
                .detail
                .contains("duplicate template name")
        );
    }

    #[cfg(unix)]
    #[test]
    fn rejects_non_utf8_bundle_paths() {
        use std::{ffi::OsString, os::unix::ffi::OsStringExt};

        let path = std::path::PathBuf::from(OsString::from_vec(vec![0xff]));
        assert!(logical_template_name(&path)
            .unwrap_err()
            .detail
            .contains("paths must be valid UTF-8"));
    }
}
