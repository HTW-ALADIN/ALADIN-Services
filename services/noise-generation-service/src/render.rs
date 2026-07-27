//! CSV rendering for the CLI's `list` and `generate` commands.
//!
//! CSV output only exists for the CLI (`POST /v1/noise` always returns JSON,
//! see `crate::error::NoiseError::UnsupportedCsv`). Living in the library
//! gives it one consistent quoting strategy and makes it unit-testable
//! without going through the CLI's argument parsing.

use crate::model::AlgorithmInfo;

/// Renders the algorithm list as CSV: one row per algorithm, with its
/// defaults rendered as a quoted, escaped JSON blob. Every field is
/// double-quoted with `"` escaped as `""` (RFC 4180); no trailing
/// human-readable summary line is appended, since that would not itself be
/// valid CSV.
pub fn list_csv(entries: &[AlgorithmInfo]) -> String {
    let mut csv = String::from("algorithm,defaults\n");
    for entry in entries {
        let defaults = entry.defaults.to_string();
        csv.push_str(&format!(
            "{},{}\n",
            csv_field(&entry.name),
            csv_field(&defaults)
        ));
    }
    csv
}

/// Renders a generated noise field's `data` (a 1D or 2D JSON array of
/// numbers) as CSV. Returns `Err` for 3D+ data, which has no natural CSV
/// representation.
pub fn generate_csv(data: &serde_json::Value, dim: usize) -> Result<String, String> {
    if dim > 2 {
        return Err(format!(
            "CSV output only supports 1D/2D noise fields; use --output-format json for {dim}D data"
        ));
    }

    let mut csv = String::new();
    let Some(rows) = data.as_array() else {
        return Ok(csv);
    };

    for row in rows {
        if let Some(values) = row.as_array() {
            // 2D: one CSV row per input row.
            let cells: Vec<String> = values
                .iter()
                .map(|v| format!("{:.6}", v.as_f64().unwrap_or(0.0)))
                .collect();
            csv.push_str(&cells.join(","));
            csv.push('\n');
        } else {
            // 1D: treat every element as its own row.
            csv.push_str(&format!("{:.6}\n", row.as_f64().unwrap_or(0.0)));
        }
    }
    Ok(csv)
}

/// Double-quotes a CSV field and escapes embedded `"` as `""` per RFC 4180.
fn csv_field(value: &str) -> String {
    format!("\"{}\"", value.replace('"', "\"\""))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generate_csv_renders_2d_rows() {
        let data = serde_json::json!([[1.0, 2.0], [3.0, 4.0]]);
        let csv = generate_csv(&data, 2).unwrap();
        assert_eq!(csv, "1.000000,2.000000\n3.000000,4.000000\n");
    }

    #[test]
    fn generate_csv_renders_1d_rows() {
        let data = serde_json::json!([1.0, 2.0, 3.0]);
        let csv = generate_csv(&data, 1).unwrap();
        assert_eq!(csv, "1.000000\n2.000000\n3.000000\n");
    }

    #[test]
    fn generate_csv_rejects_3d_plus() {
        let data = serde_json::json!([[[1.0]]]);
        assert!(generate_csv(&data, 3).is_err());
    }

    #[test]
    fn list_csv_has_no_trailing_summary_line() {
        let entries = vec![AlgorithmInfo {
            name: "perlin".to_string(),
            defaults: serde_json::json!({"seed": null}),
        }];
        let csv = list_csv(&entries);
        assert!(!csv.contains("Total"));
        assert_eq!(csv.lines().count(), 2); // header + one row
    }

    #[test]
    fn csv_field_escapes_embedded_quotes() {
        assert_eq!(csv_field(r#"has "quotes""#), r#""has ""quotes""""#);
    }
}
