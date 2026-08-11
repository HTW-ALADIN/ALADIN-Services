use std::io::{self, Write};

use axum::http::StatusCode;
use minijinja::{AutoEscape, Environment, ErrorKind};
use serde_json::Value;

use crate::{
    config::Limits,
    error::ServiceError,
    model::{
        Autoescape, RenderMetadata, RenderRequest, RenderResponse, TemplateSource,
        UndefinedBehavior,
    },
};

pub const ENGINE_NAME: &str = "minijinja";
pub const ENGINE_VERSION: &str = "2.23.0";

pub fn render(request: &RenderRequest, limits: &Limits) -> Result<RenderResponse, ServiceError> {
    validate_request(request, limits)?;

    let mut environment = Environment::new();
    environment.set_undefined_behavior(match request.options.undefined {
        UndefinedBehavior::Strict => minijinja::UndefinedBehavior::Strict,
        UndefinedBehavior::Lenient => minijinja::UndefinedBehavior::Lenient,
    });
    let autoescape = match request.options.autoescape {
        Autoescape::None => AutoEscape::None,
        Autoescape::Html => AutoEscape::Html,
    };
    environment.set_auto_escape_callback(move |_| autoescape);
    environment.set_keep_trailing_newline(request.options.keep_trailing_newline);
    environment.set_recursion_limit(limits.recursion_limit);
    environment.set_fuel(Some(limits.fuel));

    let (entrypoint, source_kind) = match &request.source {
        TemplateSource::Inline { template, name } => {
            let name = name.as_deref().unwrap_or("inline.txt").to_string();
            environment
                .add_template_owned(name.clone(), template.clone())
                .map_err(map_engine_error)?;
            (name, "inline")
        }
        TemplateSource::Bundle {
            entrypoint,
            templates,
        } => {
            for (name, source) in templates {
                environment
                    .add_template_owned(name.clone(), source.clone())
                    .map_err(map_engine_error)?;
            }
            (entrypoint.clone(), "bundle")
        }
    };

    let template = environment
        .get_template(&entrypoint)
        .map_err(map_engine_error)?;
    let mut writer = BoundedWriter::new(limits.max_output_bytes);
    let context = Value::Object(request.context.clone());
    if let Err(error) = template.render_captured_to(context, &mut writer) {
        if writer.exceeded {
            return Err(ServiceError::resource_limit(format!(
                "rendered output exceeds {} bytes",
                limits.max_output_bytes
            )));
        }
        return Err(map_engine_error(error));
    }

    let output = String::from_utf8(writer.bytes)
        .map_err(|_| ServiceError::internal("renderer produced non-UTF-8 output"))?;
    let output_bytes = output.len();
    Ok(RenderResponse {
        output,
        metadata: RenderMetadata {
            engine: ENGINE_NAME,
            engine_version: ENGINE_VERSION,
            source_kind,
            output_bytes,
        },
    })
}

fn validate_request(request: &RenderRequest, limits: &Limits) -> Result<(), ServiceError> {
    let context_bytes = serde_json::to_vec(&request.context)
        .map_err(|_| ServiceError::invalid("context could not be serialized"))?
        .len();
    if context_bytes > limits.max_context_bytes {
        return Err(ServiceError::payload_too_large(format!(
            "context exceeds {} bytes",
            limits.max_context_bytes
        )));
    }

    match &request.source {
        TemplateSource::Inline { template, name } => {
            validate_template(template, limits)?;
            if let Some(name) = name {
                validate_template_name(name, limits)?;
            }
        }
        TemplateSource::Bundle {
            entrypoint,
            templates,
        } => {
            if templates.is_empty() {
                return Err(ServiceError::invalid(
                    "bundle must contain at least one template",
                ));
            }
            if templates.len() > limits.max_bundle_templates {
                return Err(ServiceError::payload_too_large(format!(
                    "bundle contains more than {} templates",
                    limits.max_bundle_templates
                )));
            }
            validate_template_name(entrypoint, limits)?;
            if !templates.contains_key(entrypoint) {
                return Err(ServiceError::new(
                    "template-not-found",
                    StatusCode::BAD_REQUEST,
                    "Template not found",
                    "bundle entrypoint is not present in templates",
                )
                .with_location(Some(entrypoint), None));
            }
            for (name, template) in templates {
                validate_template_name(name, limits)?;
                validate_template(template, limits)?;
            }
        }
    }
    Ok(())
}

fn validate_template(template: &str, limits: &Limits) -> Result<(), ServiceError> {
    if template.len() > limits.max_template_bytes {
        return Err(ServiceError::payload_too_large(format!(
            "template exceeds {} bytes",
            limits.max_template_bytes
        )));
    }
    Ok(())
}

fn validate_template_name(name: &str, limits: &Limits) -> Result<(), ServiceError> {
    if name.is_empty() {
        return Err(ServiceError::invalid("template name must not be empty"));
    }
    if name.len() > limits.max_template_name_bytes {
        return Err(ServiceError::invalid(format!(
            "template name exceeds {} bytes",
            limits.max_template_name_bytes
        )));
    }
    if name.starts_with('/')
        || name.starts_with('\\')
        || name.contains('\0')
        || name.split(['/', '\\']).any(|segment| segment == "..")
    {
        return Err(ServiceError::invalid(
            "template name must be a relative logical name without parent traversal",
        ));
    }
    Ok(())
}

fn map_engine_error(error: minijinja::Error) -> ServiceError {
    let (code, status, title, fallback) = match error.kind() {
        ErrorKind::SyntaxError | ErrorKind::BadEscape => (
            "syntax-error",
            StatusCode::BAD_REQUEST,
            "Template syntax error",
            "template syntax is invalid",
        ),
        ErrorKind::TemplateNotFound | ErrorKind::BadInclude => (
            "template-not-found",
            StatusCode::BAD_REQUEST,
            "Template not found",
            "a referenced template is not available in the request bundle",
        ),
        ErrorKind::UndefinedError => (
            "undefined-value",
            StatusCode::BAD_REQUEST,
            "Undefined value",
            "template referenced an undefined value",
        ),
        ErrorKind::OutOfFuel => (
            "resource-limit",
            StatusCode::UNPROCESSABLE_ENTITY,
            "Resource limit exceeded",
            "template execution fuel was exhausted",
        ),
        ErrorKind::WriteFailure => (
            "render-error",
            StatusCode::BAD_REQUEST,
            "Template rendering failed",
            "renderer could not write output",
        ),
        _ => (
            "render-error",
            StatusCode::BAD_REQUEST,
            "Template rendering failed",
            "template could not be rendered",
        ),
    };
    let detail = match error.kind() {
        ErrorKind::SyntaxError | ErrorKind::BadEscape => {
            error.detail().unwrap_or(fallback).to_string()
        }
        _ => fallback.to_string(),
    };
    ServiceError::new(code, status, title, detail).with_location(error.name(), error.line())
}

struct BoundedWriter {
    bytes: Vec<u8>,
    maximum: usize,
    exceeded: bool,
}

impl BoundedWriter {
    fn new(maximum: usize) -> Self {
        Self {
            bytes: Vec::with_capacity(maximum.min(8 * 1024)),
            maximum,
            exceeded: false,
        }
    }
}

impl Write for BoundedWriter {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        if self.bytes.len().saturating_add(buffer.len()) > self.maximum {
            self.exceeded = true;
            return Err(io::Error::other("rendered output limit exceeded"));
        }
        self.bytes.extend_from_slice(buffer);
        Ok(buffer.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}
