use std::env;

pub const DEFAULT_MAX_BODY_BYTES: usize = 2 * 1024 * 1024;
pub const DEFAULT_MAX_CONTEXT_BYTES: usize = 1024 * 1024;
pub const DEFAULT_MAX_TEMPLATE_BYTES: usize = 256 * 1024;
pub const DEFAULT_MAX_BUNDLE_TEMPLATES: usize = 32;
pub const DEFAULT_MAX_TEMPLATE_NAME_BYTES: usize = 255;
pub const DEFAULT_MAX_OUTPUT_BYTES: usize = 1024 * 1024;
pub const DEFAULT_FUEL: u64 = 250_000;
pub const DEFAULT_RECURSION_LIMIT: usize = 100;
pub const DEFAULT_TIMEOUT_MS: u64 = 2_000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Limits {
    pub max_body_bytes: usize,
    pub max_context_bytes: usize,
    pub max_template_bytes: usize,
    pub max_bundle_templates: usize,
    pub max_template_name_bytes: usize,
    pub max_output_bytes: usize,
    pub fuel: u64,
    pub recursion_limit: usize,
    pub timeout_ms: u64,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            max_body_bytes: DEFAULT_MAX_BODY_BYTES,
            max_context_bytes: DEFAULT_MAX_CONTEXT_BYTES,
            max_template_bytes: DEFAULT_MAX_TEMPLATE_BYTES,
            max_bundle_templates: DEFAULT_MAX_BUNDLE_TEMPLATES,
            max_template_name_bytes: DEFAULT_MAX_TEMPLATE_NAME_BYTES,
            max_output_bytes: DEFAULT_MAX_OUTPUT_BYTES,
            fuel: DEFAULT_FUEL,
            recursion_limit: DEFAULT_RECURSION_LIMIT,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        }
    }
}

impl Limits {
    pub fn from_env() -> Result<Self, String> {
        let defaults = Self::default();
        Ok(Self {
            max_body_bytes: read_env("TEXT_TEMPLATE_MAX_BODY_BYTES", defaults.max_body_bytes)?,
            max_context_bytes: read_env(
                "TEXT_TEMPLATE_MAX_CONTEXT_BYTES",
                defaults.max_context_bytes,
            )?,
            max_template_bytes: read_env(
                "TEXT_TEMPLATE_MAX_TEMPLATE_BYTES",
                defaults.max_template_bytes,
            )?,
            max_bundle_templates: read_env(
                "TEXT_TEMPLATE_MAX_BUNDLE_TEMPLATES",
                defaults.max_bundle_templates,
            )?,
            max_template_name_bytes: read_env(
                "TEXT_TEMPLATE_MAX_TEMPLATE_NAME_BYTES",
                defaults.max_template_name_bytes,
            )?,
            max_output_bytes: read_env(
                "TEXT_TEMPLATE_MAX_OUTPUT_BYTES",
                defaults.max_output_bytes,
            )?,
            fuel: read_env("TEXT_TEMPLATE_FUEL", defaults.fuel)?,
            recursion_limit: read_env("TEXT_TEMPLATE_RECURSION_LIMIT", defaults.recursion_limit)?,
            timeout_ms: read_env("TEXT_TEMPLATE_TIMEOUT_MS", defaults.timeout_ms)?,
        })
    }
}

fn read_env<T>(name: &str, default: T) -> Result<T, String>
where
    T: std::str::FromStr,
    T::Err: std::fmt::Display,
{
    match env::var(name) {
        Ok(value) => value
            .parse()
            .map_err(|error| format!("invalid {name} value {value:?}: {error}")),
        Err(env::VarError::NotPresent) => Ok(default),
        Err(error) => Err(format!("could not read {name}: {error}")),
    }
}
