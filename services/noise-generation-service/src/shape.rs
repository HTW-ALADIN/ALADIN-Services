//! Converts a flat `&[f64]` buffer into the nested JSON shape matching the
//! requested dimensionality: 1D -> array, 2D -> nested array, 3D -> array of
//! 2D arrays, 4D -> array of 3D volumes (each volume is an array of 2D
//! slices).

use crate::dim::Dim;

pub fn shape_data(flat: &[f64], size: &[usize], dim: Dim) -> serde_json::Value {
    match dim {
        Dim::D1 => serde_json::Value::Array(flat.iter().map(|v| serde_json::json!(v)).collect()),
        Dim::D2 => {
            let w = size[0];
            serde_json::Value::Array(flat.chunks_exact(w).map(row).collect())
        }
        Dim::D3 => {
            let w = size[0];
            let h = size[1];
            serde_json::Value::Array(
                flat.chunks_exact(w * h)
                    .map(|slice| serde_json::Value::Array(slice.chunks_exact(w).map(row).collect()))
                    .collect(),
            )
        }
        Dim::D4 => {
            let w = size[0];
            let h = size[1];
            let d = size[2];
            serde_json::Value::Array(
                flat.chunks_exact(w * h * d)
                    .map(|volume| {
                        serde_json::Value::Array(
                            volume
                                .chunks_exact(w * h)
                                .map(|slice| {
                                    serde_json::Value::Array(
                                        slice.chunks_exact(w).map(row).collect(),
                                    )
                                })
                                .collect(),
                        )
                    })
                    .collect(),
            )
        }
    }
}

fn row(values: &[f64]) -> serde_json::Value {
    serde_json::Value::Array(values.iter().map(|v| serde_json::json!(v)).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shapes_1d() {
        let flat = [1.0, 2.0, 3.0];
        let shaped = shape_data(&flat, &[3], Dim::D1);
        assert_eq!(shaped, serde_json::json!([1.0, 2.0, 3.0]));
    }

    #[test]
    fn shapes_2d_row_major() {
        // 2x3 grid (w=2, h=3): flat[y*w+x]
        let flat = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0];
        let shaped = shape_data(&flat, &[2, 3], Dim::D2);
        assert_eq!(
            shaped,
            serde_json::json!([[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]])
        );
    }

    #[test]
    fn shapes_3d_has_correct_nesting_depth() {
        let flat: Vec<f64> = (0..(2 * 2 * 2)).map(|v| v as f64).collect();
        let shaped = shape_data(&flat, &[2, 2, 2], Dim::D3);
        let arr = shaped.as_array().unwrap();
        assert_eq!(arr.len(), 2); // depth
        assert_eq!(arr[0].as_array().unwrap().len(), 2); // rows
        assert_eq!(arr[0].as_array().unwrap()[0].as_array().unwrap().len(), 2); // cols
    }

    #[test]
    fn shapes_4d_has_correct_nesting_depth() {
        let flat: Vec<f64> = (0..(2 * 2 * 2 * 2)).map(|v| v as f64).collect();
        let shaped = shape_data(&flat, &[2, 2, 2, 2], Dim::D4);
        let arr = shaped.as_array().unwrap();
        assert_eq!(arr.len(), 2);
        assert_eq!(arr[0].as_array().unwrap().len(), 2);
        assert_eq!(arr[0].as_array().unwrap()[0].as_array().unwrap().len(), 2);
        assert_eq!(
            arr[0].as_array().unwrap()[0].as_array().unwrap()[0]
                .as_array()
                .unwrap()
                .len(),
            2
        );
    }
}
