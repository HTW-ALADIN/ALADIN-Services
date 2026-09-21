use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use utoipa::ToSchema;

#[derive(Debug, Clone, Deserialize, Serialize, ToSchema)]
#[serde(tag = "kind", rename_all = "lowercase", deny_unknown_fields)]
pub enum TemplateSource {
    Inline {
        template: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        name: Option<String>,
    },
    Bundle {
        entrypoint: String,
        templates: BTreeMap<String, String>,
    },
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Deserialize, Serialize, ToSchema)]
#[serde(rename_all = "lowercase")]
pub enum UndefinedBehavior {
    #[default]
    Strict,
    Lenient,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Deserialize, Serialize, ToSchema)]
#[serde(rename_all = "lowercase")]
pub enum Autoescape {
    #[default]
    None,
    Html,
}

fn default_keep_trailing_newline() -> bool {
    true
}

#[derive(Debug, Clone, Deserialize, Serialize, ToSchema)]
#[serde(default, deny_unknown_fields, rename_all = "camelCase")]
pub struct RenderOptions {
    pub undefined: UndefinedBehavior,
    pub autoescape: Autoescape,
    #[serde(default = "default_keep_trailing_newline")]
    pub keep_trailing_newline: bool,
}

impl Default for RenderOptions {
    fn default() -> Self {
        Self {
            undefined: UndefinedBehavior::Strict,
            autoescape: Autoescape::None,
            keep_trailing_newline: true,
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize, ToSchema)]
#[serde(deny_unknown_fields)]
pub struct RenderRequest {
    pub source: TemplateSource,
    pub context: Map<String, Value>,
    #[serde(default)]
    pub options: RenderOptions,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct RenderMetadata {
    pub engine: &'static str,
    pub engine_version: &'static str,
    pub source_kind: &'static str,
    pub output_bytes: usize,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
pub struct RenderResponse {
    pub output: String,
    pub metadata: RenderMetadata,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct EngineInfo {
    pub name: &'static str,
    pub version: &'static str,
    pub language: &'static str,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct FeatureInfo {
    pub variables: bool,
    pub expressions: bool,
    pub conditions: bool,
    pub loops: bool,
    pub filters: bool,
    pub tests: bool,
    pub includes: bool,
    pub inheritance: bool,
    pub macros: bool,
    pub strict_undefined: bool,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct LimitInfo {
    pub max_body_bytes: usize,
    pub max_context_bytes: usize,
    pub max_template_bytes: usize,
    pub max_bundle_templates: usize,
    pub max_template_name_bytes: usize,
    pub max_concurrent_renders: usize,
    pub max_output_bytes: usize,
    pub fuel: u64,
    pub recursion_limit: usize,
    pub timeout_ms: u64,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct CapabilitiesResponse {
    pub engine: EngineInfo,
    pub source_kinds: [&'static str; 2],
    pub context_media_type: &'static str,
    pub response_media_types: [&'static str; 2],
    pub features: FeatureInfo,
    pub limits: LimitInfo,
}

#[derive(Debug, Clone, Serialize, ToSchema)]
pub struct HealthResponse {
    pub status: &'static str,
}

#[cfg(test)]
mod tests {
    use super::default_keep_trailing_newline;

    #[test]
    fn trailing_newline_default_is_enabled() {
        assert!(default_keep_trailing_newline());
    }
}
