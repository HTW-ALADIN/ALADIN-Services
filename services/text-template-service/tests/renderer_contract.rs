use std::collections::BTreeMap;

use serde_json::{json, Map};
use text_template_service::{
    config::Limits,
    model::{RenderOptions, RenderRequest, TemplateSource},
    render,
};

fn context(value: serde_json::Value) -> Map<String, serde_json::Value> {
    value
        .as_object()
        .expect("test context is an object")
        .clone()
}

#[test]
fn renders_an_inline_template() {
    let request = RenderRequest {
        source: TemplateSource::Inline {
            template: "Hello {{ user.name }}!".to_string(),
            name: None,
        },
        context: context(json!({"user": {"name": "World"}})),
        options: RenderOptions::default(),
    };

    let response = render(&request, &Limits::default()).unwrap();
    assert_eq!(response.output, "Hello World!");
    assert_eq!(response.metadata.source_kind, "inline");
    assert_eq!(response.metadata.output_bytes, 12);
}

#[test]
fn renders_bundle_includes_and_inheritance() {
    let templates = BTreeMap::from([
        (
            "base.txt".to_string(),
            "Header\n{% block body %}{% endblock %}\nFooter".to_string(),
        ),
        (
            "message.txt".to_string(),
            "{% extends 'base.txt' %}{% block body %}{% include 'name.txt' %}{% endblock %}"
                .to_string(),
        ),
        ("name.txt".to_string(), "Hello {{ name }}".to_string()),
    ]);
    let request = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "message.txt".to_string(),
            templates,
        },
        context: context(json!({"name": "World"})),
        options: RenderOptions::default(),
    };

    let response = render(&request, &Limits::default()).unwrap();
    assert_eq!(response.output, "Header\nHello World\nFooter");
}

#[test]
fn strict_undefined_is_the_default() {
    let request = RenderRequest {
        source: TemplateSource::Inline {
            template: "{{ missing }}".to_string(),
            name: None,
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };

    let error = render(&request, &Limits::default()).unwrap_err();
    assert_eq!(error.code, "undefined-value");
}

#[test]
fn bounds_output_while_rendering() {
    let request = RenderRequest {
        source: TemplateSource::Inline {
            template: "{{ value }}".to_string(),
            name: None,
        },
        context: context(json!({"value": "123456789"})),
        options: RenderOptions::default(),
    };
    let limits = Limits {
        max_output_bytes: 8,
        ..Limits::default()
    };

    let error = render(&request, &limits).unwrap_err();
    assert_eq!(error.code, "resource-limit");
}

#[test]
fn rejects_parent_traversal_in_logical_template_names() {
    let request = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "../secret.txt".to_string(),
            templates: BTreeMap::from([("../secret.txt".to_string(), "secret".to_string())]),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };

    let error = render(&request, &Limits::default()).unwrap_err();
    assert_eq!(error.code, "invalid-request");
}

#[test]
fn missing_includes_cannot_fall_back_to_the_host_filesystem() {
    let request = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "message.txt".to_string(),
            templates: BTreeMap::from([(
                "message.txt".to_string(),
                "{% include '/etc/passwd' %}".to_string(),
            )]),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };

    let error = render(&request, &Limits::default()).unwrap_err();
    assert_eq!(error.code, "template-not-found");
}

#[test]
fn stops_templates_that_exhaust_fuel() {
    let request = RenderRequest {
        source: TemplateSource::Inline {
            template: "{% for item in range(100000) %}{{ item }}{% endfor %}".to_string(),
            name: None,
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    let limits = Limits {
        fuel: 100,
        ..Limits::default()
    };

    let error = render(&request, &limits).unwrap_err();
    assert_eq!(error.code, "resource-limit");
}
