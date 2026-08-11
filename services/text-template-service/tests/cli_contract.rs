use std::{fs, net::TcpListener, process::Stdio};

use assert_cmd::Command;
use predicates::prelude::*;

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

#[test]
fn cli_reads_an_inline_template_from_stdin() {
    let directory = tempfile::tempdir().unwrap();
    let context = directory.path().join("context.json");
    fs::write(&context, r#"{"name":"stdin"}"#).unwrap();

    Command::cargo_bin("text-template-service")
        .unwrap()
        .args(["render", "--template", "-", "--context"])
        .arg(&context)
        .write_stdin("Hello {{ name }}")
        .assert()
        .success()
        .stdout("Hello stdin");
}

#[test]
fn cli_reads_context_from_stdin() {
    let directory = tempfile::tempdir().unwrap();
    let template = directory.path().join("message.j2");
    fs::write(&template, "Hello {{ name }}").unwrap();

    Command::cargo_bin("text-template-service")
        .unwrap()
        .arg("render")
        .arg("--template")
        .arg(&template)
        .args(["--context", "-"])
        .write_stdin(r#"{"name":"context-stdin"}"#)
        .assert()
        .success()
        .stdout("Hello context-stdin");
}

#[test]
fn cli_renders_a_directory_bundle() {
    let directory = tempfile::tempdir().unwrap();
    let templates = directory.path().join("templates");
    let partials = templates.join("partials");
    fs::create_dir_all(&partials).unwrap();
    fs::write(
        templates.join("message.txt"),
        "{% include 'partials/name.txt' %}",
    )
    .unwrap();
    fs::write(partials.join("name.txt"), "Hello {{ name }}").unwrap();
    let context = directory.path().join("context.json");
    fs::write(&context, r#"{"name":"bundle"}"#).unwrap();

    Command::cargo_bin("text-template-service")
        .unwrap()
        .arg("render")
        .arg("--template-dir")
        .arg(&templates)
        .arg("--entrypoint")
        .arg("message.txt")
        .arg("--context")
        .arg(&context)
        .arg("--undefined")
        .arg("lenient")
        .arg("--autoescape")
        .arg("html")
        .arg("--strip-trailing-newline")
        .assert()
        .success()
        .stdout("Hello bundle");
}

#[test]
fn cli_generates_openapi_in_both_formats() {
    Command::cargo_bin("text-template-service")
        .unwrap()
        .args(["openapi", "--format", "json"])
        .assert()
        .success()
        .stdout(predicate::str::contains(r#""openapi": "3.1.0""#));

    let directory = tempfile::tempdir().unwrap();
    let output = directory.path().join("openapi.yaml");
    Command::cargo_bin("text-template-service")
        .unwrap()
        .arg("openapi")
        .arg("--format")
        .arg("yaml")
        .arg("--output")
        .arg(&output)
        .assert()
        .success();
    assert!(fs::read_to_string(output)
        .unwrap()
        .starts_with("openapi: 3.1.0"));
}

#[test]
fn cli_reports_configuration_and_openapi_output_errors() {
    Command::cargo_bin("text-template-service")
        .unwrap()
        .args(["openapi"])
        .env("TEXT_TEMPLATE_FUEL", "invalid")
        .assert()
        .code(2)
        .stderr(predicate::str::contains("configuration error"));

    let directory = tempfile::tempdir().unwrap();
    Command::cargo_bin("text-template-service")
        .unwrap()
        .arg("openapi")
        .arg("--output")
        .arg(directory.path())
        .assert()
        .failure()
        .stderr(predicate::str::contains("could not write OpenAPI document"));
}

#[test]
fn cli_reports_invalid_server_addresses_and_bind_failures() {
    Command::cargo_bin("text-template-service")
        .unwrap()
        .args(["server", "--host", "not-an-address"])
        .assert()
        .code(2)
        .stderr(predicate::str::contains("invalid server address"));

    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    Command::cargo_bin("text-template-service")
        .unwrap()
        .args(["server", "--host", "127.0.0.1", "--port"])
        .arg(port.to_string())
        .assert()
        .failure()
        .stderr(predicate::str::contains("could not bind"));
}

#[test]
fn cli_rejects_conflicting_stdin_and_invalid_context() {
    Command::cargo_bin("text-template-service")
        .unwrap()
        .args(["render", "--template", "-", "--context", "-"])
        .write_stdin("{}")
        .assert()
        .failure()
        .stderr(predicate::str::contains("cannot both be read from stdin"));

    let directory = tempfile::tempdir().unwrap();
    let template = directory.path().join("message.j2");
    let context = directory.path().join("context.json");
    fs::write(&template, "ok").unwrap();
    fs::write(&context, "[]").unwrap();
    Command::cargo_bin("text-template-service")
        .unwrap()
        .arg("render")
        .arg("--template")
        .arg(&template)
        .arg("--context")
        .arg(&context)
        .assert()
        .failure()
        .stderr(predicate::str::contains("context must be a JSON object"));

    fs::write(&context, "{").unwrap();
    Command::cargo_bin("text-template-service")
        .unwrap()
        .arg("render")
        .arg("--template")
        .arg(&template)
        .arg("--context")
        .arg(&context)
        .assert()
        .failure()
        .stderr(predicate::str::contains("context is not valid JSON"));
}

#[cfg(target_os = "linux")]
#[test]
fn cli_reports_stdout_write_failures() {
    let directory = tempfile::tempdir().unwrap();
    let template = directory.path().join("message.j2");
    let context = directory.path().join("context.json");
    fs::write(&template, "output".repeat(8 * 1024)).unwrap();
    fs::write(&context, "{}").unwrap();

    let child = std::process::Command::new(assert_cmd::cargo::cargo_bin!("text-template-service"))
        .arg("render")
        .arg("--template")
        .arg(&template)
        .arg("--context")
        .arg(&context)
        .stdout(fs::File::create("/dev/full").unwrap())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let output = child.wait_with_output().unwrap();

    assert!(!output.status.success());
    assert!(String::from_utf8(output.stderr)
        .unwrap()
        .contains("could not write rendered output"));
}
