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

#[test]
fn supports_lenient_undefined_and_html_autoescaping() {
    let request = RenderRequest {
        source: TemplateSource::Inline {
            template: "{{ missing }}{{ value }}".to_string(),
            name: Some("message.html".to_string()),
        },
        context: context(json!({"value": "<strong>safe</strong>"})),
        options: RenderOptions {
            undefined: text_template_service::model::UndefinedBehavior::Lenient,
            autoescape: text_template_service::model::Autoescape::Html,
            keep_trailing_newline: true,
        },
    };

    let response = render(&request, &Limits::default()).unwrap();
    assert_eq!(response.output, "&lt;strong&gt;safe&lt;&#x2f;strong&gt;");
}

#[test]
fn enforces_context_and_template_size_limits() {
    let context_request = RenderRequest {
        source: TemplateSource::Inline {
            template: "ok".to_string(),
            name: None,
        },
        context: context(json!({"value": "too large"})),
        options: RenderOptions::default(),
    };
    let context_error = render(
        &context_request,
        &Limits {
            max_context_bytes: 2,
            ..Limits::default()
        },
    )
    .unwrap_err();
    assert_eq!(
        context_error.status,
        axum::http::StatusCode::PAYLOAD_TOO_LARGE
    );

    let template_request = RenderRequest {
        source: TemplateSource::Inline {
            template: "too large".to_string(),
            name: None,
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    let template_error = render(
        &template_request,
        &Limits {
            max_template_bytes: 2,
            ..Limits::default()
        },
    )
    .unwrap_err();
    assert_eq!(
        template_error.status,
        axum::http::StatusCode::PAYLOAD_TOO_LARGE
    );
}

#[test]
fn validates_bundle_shape_and_entrypoint() {
    let empty = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "message.txt".to_string(),
            templates: BTreeMap::new(),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    assert_eq!(
        render(&empty, &Limits::default()).unwrap_err().code,
        "invalid-request"
    );

    let missing = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "missing.txt".to_string(),
            templates: BTreeMap::from([("message.txt".to_string(), "ok".to_string())]),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    assert_eq!(
        render(&missing, &Limits::default()).unwrap_err().code,
        "template-not-found"
    );

    let too_many = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "one.txt".to_string(),
            templates: BTreeMap::from([
                ("one.txt".to_string(), "one".to_string()),
                ("two.txt".to_string(), "two".to_string()),
            ]),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    let error = render(
        &too_many,
        &Limits {
            max_bundle_templates: 1,
            ..Limits::default()
        },
    )
    .unwrap_err();
    assert_eq!(error.status, axum::http::StatusCode::PAYLOAD_TOO_LARGE);
}

#[test]
fn validates_empty_and_oversized_template_names() {
    for (name, maximum) in [("", 255), ("long-name.txt", 4)] {
        let request = RenderRequest {
            source: TemplateSource::Inline {
                template: "ok".to_string(),
                name: Some(name.to_string()),
            },
            context: Map::new(),
            options: RenderOptions::default(),
        };
        let error = render(
            &request,
            &Limits {
                max_template_name_bytes: maximum,
                ..Limits::default()
            },
        )
        .unwrap_err();
        assert_eq!(error.code, "invalid-request");
    }
}

#[test]
fn validates_each_template_inside_a_bundle() {
    let invalid_name = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "message.txt".to_string(),
            templates: BTreeMap::from([
                ("message.txt".to_string(), "ok".to_string()),
                ("".to_string(), "invalid".to_string()),
            ]),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    assert_eq!(
        render(&invalid_name, &Limits::default()).unwrap_err().code,
        "invalid-request"
    );

    let oversized = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "message.txt".to_string(),
            templates: BTreeMap::from([
                ("message.txt".to_string(), "ok".to_string()),
                ("other.txt".to_string(), "oversized".to_string()),
            ]),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    let error = render(
        &oversized,
        &Limits {
            max_template_bytes: 4,
            ..Limits::default()
        },
    )
    .unwrap_err();
    assert_eq!(error.status, axum::http::StatusCode::PAYLOAD_TOO_LARGE);

    let syntax_error = RenderRequest {
        source: TemplateSource::Bundle {
            entrypoint: "message.txt".to_string(),
            templates: BTreeMap::from([("message.txt".to_string(), "{% if %}".to_string())]),
        },
        context: Map::new(),
        options: RenderOptions::default(),
    };
    assert_eq!(
        render(&syntax_error, &Limits::default()).unwrap_err().code,
        "syntax-error"
    );
}
