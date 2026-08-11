use std::fs;

use assert_cmd::Command;

#[test]
fn cli_renders_the_same_inline_contract() {
    let directory = tempfile::tempdir().unwrap();
    let template = directory.path().join("message.j2");
    let context = directory.path().join("context.json");
    fs::write(&template, "Hello {{ name }}!").unwrap();
    fs::write(&context, r#"{"name":"World"}"#).unwrap();

    Command::cargo_bin("text-template-service")
        .unwrap()
        .args([
            "render",
            "--template",
            template.to_str().unwrap(),
            "--context",
            context.to_str().unwrap(),
        ])
        .assert()
        .success()
        .stdout("Hello World!");
}

#[test]
fn cli_returns_structured_errors() {
    let directory = tempfile::tempdir().unwrap();
    let template = directory.path().join("message.j2");
    let context = directory.path().join("context.json");
    fs::write(&template, "{{ missing }}").unwrap();
    fs::write(&context, "{}").unwrap();

    Command::cargo_bin("text-template-service")
        .unwrap()
        .args([
            "render",
            "--template",
            template.to_str().unwrap(),
            "--context",
            context.to_str().unwrap(),
        ])
        .assert()
        .failure()
        .stderr(predicates::str::contains("undefined-value"));
}
