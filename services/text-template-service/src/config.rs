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

#[cfg(test)]
mod tests {
    use std::{env, ffi::OsString, sync::Mutex};

    use super::Limits;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    const VARIABLES: [&str; 9] = [
        "TEXT_TEMPLATE_MAX_BODY_BYTES",
        "TEXT_TEMPLATE_MAX_CONTEXT_BYTES",
        "TEXT_TEMPLATE_MAX_TEMPLATE_BYTES",
        "TEXT_TEMPLATE_MAX_BUNDLE_TEMPLATES",
        "TEXT_TEMPLATE_MAX_TEMPLATE_NAME_BYTES",
        "TEXT_TEMPLATE_MAX_OUTPUT_BYTES",
        "TEXT_TEMPLATE_FUEL",
        "TEXT_TEMPLATE_RECURSION_LIMIT",
        "TEXT_TEMPLATE_TIMEOUT_MS",
    ];

    struct EnvCleanup;

    impl Drop for EnvCleanup {
        fn drop(&mut self) {
            for variable in VARIABLES {
                env::remove_var(variable);
            }
        }
    }

    #[test]
    fn reads_every_limit_from_the_environment() {
        let _lock = ENV_LOCK.lock().unwrap();
        let _cleanup = EnvCleanup;
        for (index, variable) in VARIABLES.into_iter().enumerate() {
            env::set_var(variable, (index + 1).to_string());
        }

        let limits = Limits::from_env().unwrap();

        assert_eq!(limits.max_body_bytes, 1);
        assert_eq!(limits.max_context_bytes, 2);
        assert_eq!(limits.max_template_bytes, 3);
        assert_eq!(limits.max_bundle_templates, 4);
        assert_eq!(limits.max_template_name_bytes, 5);
        assert_eq!(limits.max_output_bytes, 6);
        assert_eq!(limits.fuel, 7);
        assert_eq!(limits.recursion_limit, 8);
        assert_eq!(limits.timeout_ms, 9);
    }

    #[test]
    fn rejects_invalid_numeric_values() {
        let _lock = ENV_LOCK.lock().unwrap();
        let _cleanup = EnvCleanup;
        for variable in VARIABLES {
            env::set_var(variable, "not-a-number");
            let error = Limits::from_env().unwrap_err();
            assert!(error.contains(&format!("invalid {variable} value")));
            env::remove_var(variable);
        }
    }

    #[cfg(unix)]
    #[test]
    fn rejects_non_unicode_values() {
        use std::os::unix::ffi::OsStringExt;

        let _lock = ENV_LOCK.lock().unwrap();
        let _cleanup = EnvCleanup;
        env::set_var("TEXT_TEMPLATE_TIMEOUT_MS", OsString::from_vec(vec![0xff]));

        let error = Limits::from_env().unwrap_err();

        assert!(error.contains("could not read TEXT_TEMPLATE_TIMEOUT_MS"));
    }
}
