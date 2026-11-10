use std::io::{self, Write};

use minijinja::value::{Kwargs, Rest, StringInput};
use minijinja::{Error, ErrorKind, State, Value};

use crate::config::DEFAULT_MAX_OUTPUT_BYTES;

/// Detail attached to errors raised when a bounded filter would have to
/// materialize an output larger than the service output limit.
///
/// The renderer translates errors carrying this detail into the same
/// `resource-limit`/422 response that the top-level output writer produces.
pub const OUTPUT_LIMIT_DETAIL: &str = "rendered output would exceed the output limit";

/// Maximum number of bytes a single filter value is allowed to materialize.
///
/// MiniJinja filters build their result as an in-memory `Value` before the
/// renderer's bounded writer sees it, so a filter must stop building once the
/// configured output limit is reached.  This is kept in sync with the default
/// output limit; deployments that raise `TEXT_TEMPLATE_MAX_OUTPUT_BYTES`
/// above the default accept a slightly stricter per-filter ceiling.
const OUTPUT_BUDGET: usize = DEFAULT_MAX_OUTPUT_BYTES;

/// Upper bound for the `tojson` pretty-print indent width.  The indent string
/// is allocated up front by serde_json, so unbounded widths must be rejected
/// instead of allocated.
const MAX_TOJSON_INDENT: usize = 64 * 1024;

/// Upper bound for printf field widths and precisions in the `format` filter.
/// The printf engine repeats the fill character `width` times, so absurd
/// widths must be clamped before the built-in filter sees them.
const MAX_PRINTF_WIDTH: u64 = 256;

/// Replaces the built-in `indent`, `tojson`, and `format` filters with bounded
/// equivalents so that attacker-controlled widths can never trigger a giant
/// allocation that aborts the process (MiniJinja issue #924 family).
pub fn register(environment: &mut minijinja::Environment<'static>) {
    environment.add_filter("indent", indent);
    environment.add_filter("tojson", tojson);
    environment.add_filter("format", format);
}

fn limit_error() -> Error {
    Error::new(ErrorKind::InvalidOperation, OUTPUT_LIMIT_DETAIL)
}

fn push_bounded(out: &mut Vec<u8>, bytes: &[u8]) -> Result<(), Error> {
    if out.len().saturating_add(bytes.len()) > OUTPUT_BUDGET {
        return Err(limit_error());
    }
    out.extend_from_slice(bytes);
    Ok(())
}

fn push_spaces(out: &mut Vec<u8>, count: usize) -> Result<(), Error> {
    if out.len().saturating_add(count) > OUTPUT_BUDGET {
        return Err(limit_error());
    }
    out.resize(out.len() + count, b' ');
    Ok(())
}

/// Bounded replacement for the `indent` filter.
///
/// Mirrors MiniJinja's implementation semantics but never allocates an
/// `indent_with` string of `width` bytes and stops building as soon as the
/// output would exceed [`OUTPUT_BUDGET`].
fn indent(
    value: StringInput<'_>,
    width: Option<usize>,
    indent_first_line: Option<bool>,
    indent_blank_lines: Option<bool>,
    kwargs: Kwargs,
) -> Result<Value, Error> {
    let width = match width {
        Some(width) => width,
        None => kwargs.get::<Option<usize>>("width")?.unwrap_or(4),
    };
    let indent_first_line = match indent_first_line {
        Some(value) => value,
        None => kwargs.get::<Option<bool>>("first")?.unwrap_or(false),
    };
    let indent_blank_lines = match indent_blank_lines {
        Some(value) => value,
        None => kwargs.get::<Option<bool>>("blank")?.unwrap_or(false),
    };
    kwargs.assert_all_used()?;

    let mut input = value.as_str();
    if let Some(stripped) = input.strip_suffix('\n') {
        input = stripped;
    }
    if let Some(stripped) = input.strip_suffix('\r') {
        input = stripped;
    }

    let mut out: Vec<u8> = Vec::new();
    let mut lines = input.split('\n');
    if !indent_first_line {
        if let Some(first) = lines.next() {
            push_bounded(&mut out, first.as_bytes())?;
            push_bounded(&mut out, b"\n")?;
        }
    }
    for line in lines {
        if line.is_empty() {
            if indent_blank_lines {
                push_spaces(&mut out, width)?;
            }
        } else {
            push_spaces(&mut out, width)?;
            push_bounded(&mut out, line.as_bytes())?;
        }
        push_bounded(&mut out, b"\n")?;
    }

    let mut output = String::from_utf8(out)
        .map_err(|_| Error::new(ErrorKind::InvalidOperation, "indent produced invalid UTF-8"))?;
    if output.ends_with('\n') {
        output.pop();
        if output.ends_with('\r') {
            output.pop();
        }
    }
    Ok(value.preserve_safety(output))
}

struct BudgetWriter {
    bytes: Vec<u8>,
    exceeded: bool,
}

impl BudgetWriter {
    fn new() -> Self {
        Self {
            bytes: Vec::new(),
            exceeded: false,
        }
    }
}

impl Write for BudgetWriter {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        if self.bytes.len().saturating_add(buffer.len()) > OUTPUT_BUDGET {
            self.exceeded = true;
            return Err(io::Error::other(OUTPUT_LIMIT_DETAIL));
        }
        self.bytes.extend_from_slice(buffer);
        Ok(buffer.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

/// Bounded replacement for the `tojson` filter.
///
/// Mirrors MiniJinja's implementation but serializes through [`BudgetWriter`]
/// and rejects pretty-print indent widths that would require an oversized
/// upfront allocation.
fn tojson(value: &Value, indent: Option<Value>, args: Kwargs) -> Result<Value, Error> {
    let indent = match indent {
        Some(indent) => Some(indent),
        None => args.get::<Option<Value>>("indent")?,
    };
    let indent = match indent {
        None => None,
        Some(ref val) => match bool::try_from(val.clone()).ok() {
            Some(true) => Some(2usize),
            Some(false) => None,
            None => Some(usize::try_from(val.clone())?),
        },
    };
    args.assert_all_used()?;
    let indent = match indent {
        Some(indent) if indent > MAX_TOJSON_INDENT => return Err(limit_error()),
        indent => indent,
    };

    let mut out = BudgetWriter::new();
    let serialized = if let Some(indent) = indent {
        let indentation = vec![b' '; indent];
        let formatter = serde_json::ser::PrettyFormatter::with_indent(&indentation);
        let mut serializer = serde_json::ser::Serializer::with_formatter(&mut out, formatter);
        serde::Serialize::serialize(value, &mut serializer)
    } else {
        serde_json::to_writer(&mut out, value)
    };
    if let Err(error) = serialized {
        if out.exceeded {
            return Err(limit_error());
        }
        return Err(
            Error::new(ErrorKind::InvalidOperation, "cannot serialize to JSON").with_source(error),
        );
    }

    let mut escaped: Vec<u8> = Vec::new();
    for &byte in &out.bytes {
        let chunk: &[u8] = match byte {
            b'<' => b"\\u003c",
            b'>' => b"\\u003e",
            b'&' => b"\\u0026",
            b'\'' => b"\\u0027",
            _ => std::slice::from_ref(&byte),
        };
        if escaped.len().saturating_add(chunk.len()) > OUTPUT_BUDGET {
            return Err(limit_error());
        }
        escaped.extend_from_slice(chunk);
    }
    let output = String::from_utf8(escaped)
        .map_err(|_| Error::new(ErrorKind::InvalidOperation, "tojson produced invalid UTF-8"))?;
    Ok(Value::from_safe_string(output))
}

/// Bounded replacement for the `format` filter.
///
/// Clamps oversized printf field widths/precisions in the format string before
/// delegating to the built-in filter, so the printf engine never repeats a fill
/// character an unbounded number of times.
fn format(state: &State, format_str: &Value, format_args: Rest<Value>) -> Result<Value, Error> {
    let spec = match format_str.as_str() {
        Some(spec) => spec,
        None => return minijinja_format_filter(state, format_str, format_args),
    };
    let clamped = match clamp_printf_widths(spec) {
        Some(clamped) => clamped,
        None => return minijinja_format_filter(state, format_str, format_args),
    };
    let clamped_value = if format_str.is_safe() {
        Value::from_safe_string(clamped)
    } else {
        Value::from(clamped)
    };
    minijinja_format_filter(state, &clamped_value, format_args)
}

/// Rewrites printf-style width/precision runs that exceed [`MAX_PRINTF_WIDTH`]
/// down to that bound.  Returns `None` when the spec needs no rewriting.
fn clamp_printf_widths(spec: &str) -> Option<String> {
    if !printf_has_oversized_fields(spec) {
        return None;
    }
    let bytes = spec.as_bytes();
    let mut out = String::with_capacity(spec.len());
    let mut copy_from = 0usize;
    let mut index = 0usize;
    while index < bytes.len() {
        if bytes[index] != b'%' {
            index += 1;
            continue;
        }
        let Some(parsed) = parse_printf_field(bytes, index) else {
            index += 1;
            continue;
        };
        out.push_str(&spec[copy_from..index]);
        out.push('%');
        let mut cursor = index + 1;
        while cursor < parsed.flags_end {
            out.push(bytes[cursor] as char);
            cursor += 1;
        }
        cursor = push_clamped_run(&mut out, bytes, parsed.width, cursor);
        if parsed.precision.is_some() {
            out.push('.');
            if let Some((start, end)) = parsed.precision {
                let value = decimal_value(bytes, start, end);
                if value > MAX_PRINTF_WIDTH {
                    out.push_str(&MAX_PRINTF_WIDTH.to_string());
                } else {
                    out.push_str(&spec[start..end]);
                }
            }
            cursor = parsed.precision.map_or(cursor, |(_, end)| end);
        }
        out.push_str(&spec[cursor..parsed.end]);
        copy_from = parsed.end;
        index = parsed.end;
    }
    out.push_str(&spec[copy_from..]);
    Some(out)
}

fn push_clamped_run(
    out: &mut String,
    bytes: &[u8],
    width: Option<(usize, usize)>,
    mut cursor: usize,
) -> usize {
    if let Some((start, end)) = width {
        let value = decimal_value(bytes, start, end);
        if value > MAX_PRINTF_WIDTH {
            out.push_str(&MAX_PRINTF_WIDTH.to_string());
        } else {
            out.push_str(std::str::from_utf8(&bytes[start..end]).unwrap_or("0"));
        }
        cursor = end;
    }
    cursor
}

#[derive(Clone, Copy)]
struct ParsedField {
    flags_end: usize,
    width: Option<(usize, usize)>,
    precision: Option<(usize, usize)>,
    end: usize,
}

fn printf_has_oversized_fields(spec: &str) -> bool {
    let bytes = spec.as_bytes();
    let mut index = 0usize;
    while index < bytes.len() {
        if bytes[index] != b'%' {
            index += 1;
            continue;
        }
        let Some(parsed) = parse_printf_field(bytes, index) else {
            index += 1;
            continue;
        };
        for run in [parsed.width, parsed.precision].into_iter().flatten() {
            if decimal_value(bytes, run.0, run.1) > MAX_PRINTF_WIDTH {
                return true;
            }
        }
        index = parsed.end;
    }
    false
}

fn parse_printf_field(bytes: &[u8], index: usize) -> Option<ParsedField> {
    let mut cursor = index + 1;
    if cursor < bytes.len() && bytes[cursor] == b'%' {
        return None;
    }
    if cursor < bytes.len() && bytes[cursor] == b'(' {
        return None;
    }
    while cursor < bytes.len() && matches!(bytes[cursor], b'#' | b'0' | b'-' | b'+' | b' ') {
        cursor += 1;
    }
    let flags_end = cursor;
    let width = digit_run(bytes, cursor).inspect(|(_, end)| cursor = *end);
    let mut precision = None;
    if cursor < bytes.len() && bytes[cursor] == b'.' {
        if let Some(run) = digit_run(bytes, cursor + 1) {
            precision = Some(run);
            cursor = run.1;
        }
    }
    if cursor < bytes.len() && matches!(bytes[cursor], b'h' | b'l' | b'L') {
        cursor += 1;
    }
    if cursor < bytes.len() && is_printf_type(bytes[cursor]) {
        Some(ParsedField {
            flags_end,
            width,
            precision,
            end: cursor + 1,
        })
    } else {
        None
    }
}

fn digit_run(bytes: &[u8], mut cursor: usize) -> Option<(usize, usize)> {
    let start = cursor;
    while cursor < bytes.len() && bytes[cursor].is_ascii_digit() {
        cursor += 1;
    }
    if cursor == start {
        None
    } else {
        Some((start, cursor))
    }
}

fn decimal_value(bytes: &[u8], start: usize, end: usize) -> u64 {
    bytes[start..end].iter().fold(0u64, |value, byte| {
        value
            .saturating_mul(10)
            .saturating_add(u64::from(byte - b'0'))
    })
}

fn is_printf_type(byte: u8) -> bool {
    matches!(
        byte,
        b'd' | b'i'
            | b'o'
            | b'x'
            | b'X'
            | b'e'
            | b'E'
            | b'f'
            | b'F'
            | b'g'
            | b'G'
            | b'c'
            | b's'
            | b'r'
            | b'a'
    )
}

use minijinja::filters::format as minijinja_format_filter;

#[cfg(test)]
mod tests {
    use minijinja::{Environment, Value};

    use super::clamp_printf_widths;

    #[test]
    fn clamps_only_oversized_printf_widths() {
        assert_eq!(clamp_printf_widths("%05d-%s-%%"), None);
        assert_eq!(clamp_printf_widths("%2000000000d"), Some("%256d".into()));
        assert_eq!(clamp_printf_widths("%.200f"), None);
        assert_eq!(clamp_printf_widths("%.2000f"), Some("%.256f".into()));
        assert_eq!(
            clamp_printf_widths("x %0500000000d y %.9f z %+20s"),
            Some("x %0256d y %.9f z %+20s".into())
        );
        assert_eq!(clamp_printf_widths("50% of %d is fine"), None);
        assert_eq!(clamp_printf_widths("literal 100%"), None);
    }

    #[test]
    fn bounded_format_clamps_giant_widths() {
        let mut environment = Environment::new();
        super::register(&mut environment);
        let rendered = environment
            .render_str(r#"{{ "%02000000000d"|format(1) }}"#, Value::UNDEFINED)
            .unwrap();
        assert_eq!(rendered.len(), 256);
        assert!(rendered.ends_with('1'));
        assert!(rendered.bytes().all(|byte| byte == b'0' || byte == b'1'));
    }
}
