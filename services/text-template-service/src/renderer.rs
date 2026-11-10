use std::collections::{HashMap, VecDeque};
use std::io::{self, Write};
use std::sync::{Arc, Mutex};

use axum::http::StatusCode;
use minijinja::{AutoEscape, Environment, ErrorKind};
use serde_json::Value;

use crate::{
    bounded_filters,
    config::Limits,
    error::ServiceError,
    model::{
        Autoescape, RenderMetadata, RenderRequest, RenderResponse, TemplateSource,
        UndefinedBehavior,
    },
};

pub const ENGINE_NAME: &str = "minijinja";
pub const ENGINE_VERSION: &str = "2.24.0";

const CACHE_MAX_ENTRIES: usize = 32;
const CACHE_MAX_RETAINED_BYTES: usize = 8 * 1024 * 1024;
/// Multiplier applied to template source bytes to approximate the memory a
/// cached entry actually retains (the key itself, the template sources the
/// engine keeps per loaded template, and the compiled bytecode).
const CACHE_MEMORY_WEIGHT_FACTOR: usize = 3;

pub fn render(request: &RenderRequest, limits: &Limits) -> Result<RenderResponse, ServiceError> {
    validate_request(request, limits)?;
    let compiled = build_environment(request, limits)?;
    execute(compiled, request, limits)
}

pub fn render_cached(
    request: &RenderRequest,
    limits: &Limits,
    cache: &TemplateCache,
) -> Result<RenderResponse, ServiceError> {
    validate_request(request, limits)?;
    let key = CacheKey::from_request(request, limits);
    let compiled = match cache.get(&key) {
        Some(environment) => CompiledEnvironment {
            environment,
            entrypoint: key.entrypoint.clone(),
            source_kind: source_kind_of(request),
        },
        None => {
            let compiled = build_environment(request, limits)?;
            cache.insert(key, compiled.environment.clone());
            compiled
        }
    };
    execute(compiled, request, limits)
}

struct CompiledEnvironment {
    environment: Arc<Environment<'static>>,
    entrypoint: String,
    source_kind: &'static str,
}

fn build_environment(
    request: &RenderRequest,
    limits: &Limits,
) -> Result<CompiledEnvironment, ServiceError> {
    let mut environment: Environment<'static> = Environment::new();
    bounded_filters::register(&mut environment);
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
            let name = inline_name(name);
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
    Ok(CompiledEnvironment {
        environment: Arc::new(environment),
        entrypoint,
        source_kind,
    })
}

fn inline_name(name: &Option<String>) -> String {
    name.clone().unwrap_or_else(|| "inline.txt".to_string())
}

fn source_kind_of(request: &RenderRequest) -> &'static str {
    match &request.source {
        TemplateSource::Inline { .. } => "inline",
        TemplateSource::Bundle { .. } => "bundle",
    }
}

fn execute(
    compiled: CompiledEnvironment,
    request: &RenderRequest,
    limits: &Limits,
) -> Result<RenderResponse, ServiceError> {
    let template = compiled
        .environment
        .get_template(&compiled.entrypoint)
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
        if error.detail() == Some(bounded_filters::OUTPUT_LIMIT_DETAIL) {
            return Err(ServiceError::resource_limit(
                bounded_filters::OUTPUT_LIMIT_DETAIL,
            ));
        }
        return Err(map_engine_error(error));
    }

    let output = String::from_utf8_lossy(&writer.bytes).into_owned();
    let output_bytes = output.len();
    Ok(RenderResponse {
        output,
        metadata: RenderMetadata {
            engine: ENGINE_NAME,
            engine_version: ENGINE_VERSION,
            source_kind: compiled.source_kind,
            output_bytes,
        },
    })
}

#[derive(Clone)]
pub struct TemplateCache {
    inner: Arc<Mutex<CacheState>>,
}

impl Default for TemplateCache {
    fn default() -> Self {
        Self {
            inner: Arc::new(Mutex::new(CacheState::default())),
        }
    }
}

impl TemplateCache {
    pub fn new() -> Self {
        Self::default()
    }

    fn get(&self, key: &CacheKey) -> Option<Arc<Environment<'static>>> {
        let state = cache_lock(&self.inner);
        state.entries.get(key).cloned()
    }

    fn insert(&self, key: CacheKey, environment: Arc<Environment<'static>>) {
        let mut state = cache_lock(&self.inner);
        if state.entries.contains_key(&key) {
            return;
        }
        let added_weight = key.retained_weight();
        if added_weight > CACHE_MAX_RETAINED_BYTES {
            // Never admit a single entry that exceeds the whole budget; it is
            // still rendered (the compiled environment is returned to the
            // caller), just not retained.
            return;
        }
        while !state.order.is_empty()
            && (state.entries.len() >= CACHE_MAX_ENTRIES
                || state.retained_bytes.saturating_add(added_weight) > CACHE_MAX_RETAINED_BYTES)
        {
            let Some(oldest) = state.order.pop_front() else {
                break;
            };
            if state.entries.remove(oldest.as_ref()).is_some() {
                state.retained_bytes = state
                    .retained_bytes
                    .saturating_sub(oldest.retained_weight());
            }
        }
        let key = Arc::new(key);
        state.entries.insert(key.clone(), environment);
        state.order.push_back(key);
        state.retained_bytes = state.retained_bytes.saturating_add(added_weight);
    }
}

fn cache_lock(inner: &Mutex<CacheState>) -> std::sync::MutexGuard<'_, CacheState> {
    inner
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

#[derive(Default)]
struct CacheState {
    entries: HashMap<Arc<CacheKey>, Arc<Environment<'static>>>,
    order: VecDeque<Arc<CacheKey>>,
    retained_bytes: usize,
}

#[derive(Clone, PartialEq, Eq, Hash)]
struct CacheKey {
    entrypoint: String,
    templates: Vec<(String, String)>,
    autoescape: Autoescape,
    undefined: UndefinedBehavior,
    keep_trailing_newline: bool,
    recursion_limit: usize,
    fuel: u64,
}

impl CacheKey {
    fn from_request(request: &RenderRequest, limits: &Limits) -> Self {
        let (entrypoint, templates) = match &request.source {
            TemplateSource::Inline { template, name } => {
                let name = inline_name(name);
                (name.clone(), vec![(name, template.clone())])
            }
            TemplateSource::Bundle {
                entrypoint,
                templates,
            } => (
                entrypoint.clone(),
                templates
                    .iter()
                    .map(|(name, source)| (name.clone(), source.clone()))
                    .collect(),
            ),
        };
        Self {
            entrypoint,
            templates,
            autoescape: request.options.autoescape,
            undefined: request.options.undefined,
            keep_trailing_newline: request.options.keep_trailing_newline,
            recursion_limit: limits.recursion_limit,
            fuel: limits.fuel,
        }
    }

    fn template_bytes(&self) -> usize {
        self.templates
            .iter()
            .map(|(name, source)| name.len() + source.len())
            .sum()
    }

    fn retained_weight(&self) -> usize {
        self.template_bytes()
            .saturating_mul(CACHE_MEMORY_WEIGHT_FACTOR)
    }
}

fn validate_request(request: &RenderRequest, limits: &Limits) -> Result<(), ServiceError> {
    let context_bytes = serde_json::to_vec(&request.context)
        .expect("serde_json::Value objects are always serializable")
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

#[cfg(test)]
mod tests {
    use std::io::Write;

    use minijinja::{Error, ErrorKind};
    use serde_json::json;

    use super::{map_engine_error, render, render_cached, BoundedWriter, TemplateCache};
    use crate::config::Limits;
    use crate::model::{Autoescape, RenderOptions, RenderRequest, TemplateSource};

    #[test]
    fn maps_write_and_generic_engine_errors() {
        let write_error = map_engine_error(Error::new(ErrorKind::WriteFailure, "write failed"));
        assert_eq!(write_error.code, "render-error");
        assert_eq!(write_error.detail, "renderer could not write output");

        let generic_error = map_engine_error(Error::new(ErrorKind::InvalidOperation, "invalid"));
        assert_eq!(generic_error.code, "render-error");
        assert_eq!(generic_error.detail, "template could not be rendered");
    }

    #[test]
    fn bounded_writer_flushes_successfully() {
        let mut writer = BoundedWriter::new(4);
        writer.write_all(b"test").unwrap();
        writer.flush().unwrap();
    }

    #[test]
    fn cached_render_matches_uncached_output() {
        let cache = TemplateCache::new();
        let limits = Limits::default();
        let request = RenderRequest {
            source: TemplateSource::Inline {
                template: "Hello {{ name }}".to_string(),
                name: Some("greeting.j2".to_string()),
            },
            context: json!({ "name": "world" })
                .as_object()
                .cloned()
                .unwrap_or_default(),
            options: RenderOptions::default(),
        };

        let expected = render(&request, &limits).unwrap().output;
        let first = render_cached(&request, &limits, &cache).unwrap().output;
        let second = render_cached(&request, &limits, &cache).unwrap().output;

        assert_eq!(first, expected);
        assert_eq!(second, expected);
    }

    #[test]
    fn cached_renders_do_not_mix_autoescape_options() {
        let cache = TemplateCache::new();
        let limits = Limits::default();
        let mut request = RenderRequest {
            source: TemplateSource::Inline {
                template: "{{ value }}".to_string(),
                name: None,
            },
            context: json!({ "value": "<b>bold</b>" })
                .as_object()
                .cloned()
                .unwrap_or_default(),
            options: RenderOptions {
                autoescape: Autoescape::Html,
                ..RenderOptions::default()
            },
        };

        let escaped = render_cached(&request, &limits, &cache).unwrap().output;
        assert_eq!(escaped, "&lt;b&gt;bold&lt;&#x2f;b&gt;");

        request.options.autoescape = Autoescape::None;
        let raw = render_cached(&request, &limits, &cache).unwrap().output;
        assert_eq!(raw, "<b>bold</b>");
    }
}
