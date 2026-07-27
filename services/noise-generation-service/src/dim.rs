//! Dimensionality of a sampling grid, and shared per-cell iteration helpers.
//!
//! Every generation kernel used to accept `mode: &str` with values like
//! `"2d"`/`"3d"`/`"4d"` — a typo (e.g. `"2D"`) would silently fall through to
//! `unreachable!()` and panic at runtime. `Dim` makes the set of supported
//! dimensionalities a compile-time-checked enum instead.

use std::fmt;

/// The coordinate scaling factor applied to noise-crate/FastNoiseLite sample
/// positions. Named so every generation kernel shares one definition instead
/// of repeating the bare literal `0.1` at each call site.
pub const COORD_STEP: f64 = 0.1;

/// Supported sampling dimensionalities (1D-4D). 5D+ is rejected by every
/// algorithm and is therefore not representable by this type.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Dim {
    D1,
    D2,
    D3,
    D4,
}

impl Dim {
    /// Maps a `sampling.size` length to a `Dim`, or `None` for unsupported
    /// (0 or 5+) lengths.
    pub fn from_len(len: usize) -> Option<Dim> {
        match len {
            1 => Some(Dim::D1),
            2 => Some(Dim::D2),
            3 => Some(Dim::D3),
            4 => Some(Dim::D4),
            _ => None,
        }
    }

    pub fn as_usize(&self) -> usize {
        match self {
            Dim::D1 => 1,
            Dim::D2 => 2,
            Dim::D3 => 3,
            Dim::D4 => 4,
        }
    }
}

impl fmt::Display for Dim {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}D", self.as_usize())
    }
}

/// Row-major cell iteration for a 2D grid: yields `(flat_index, [x, y])`.
///
/// Implemented as an explicit `Iterator` (incrementing plain coordinate/index
/// counters) rather than a nested `flat_map`/`map` chain: the flat_map form
/// recomputes each flat index from scratch per cell (e.g. `y * w + x`),
/// which is measurably slower than a running increment for the cheaper
/// kernels (white noise, `Utility::Constant`) where index bookkeeping is a
/// larger fraction of the per-cell cost.
pub fn iter_2d(size: &[usize]) -> Cells2D {
    Cells2D {
        w: size[0],
        h: size[1],
        x: 0,
        y: 0,
        idx: 0,
    }
}

pub struct Cells2D {
    w: usize,
    h: usize,
    x: usize,
    y: usize,
    idx: usize,
}

impl Iterator for Cells2D {
    type Item = (usize, [usize; 2]);

    fn next(&mut self) -> Option<Self::Item> {
        if self.y >= self.h {
            return None;
        }
        let item = (self.idx, [self.x, self.y]);
        self.idx += 1;
        self.x += 1;
        if self.x >= self.w {
            self.x = 0;
            self.y += 1;
        }
        Some(item)
    }
}

/// Row-major cell iteration for a 3D grid: yields `(flat_index, [x, y, z])`.
pub fn iter_3d(size: &[usize]) -> Cells3D {
    Cells3D {
        w: size[0],
        h: size[1],
        d: size[2],
        x: 0,
        y: 0,
        z: 0,
        idx: 0,
    }
}

pub struct Cells3D {
    w: usize,
    h: usize,
    d: usize,
    x: usize,
    y: usize,
    z: usize,
    idx: usize,
}

impl Iterator for Cells3D {
    type Item = (usize, [usize; 3]);

    fn next(&mut self) -> Option<Self::Item> {
        if self.z >= self.d {
            return None;
        }
        let item = (self.idx, [self.x, self.y, self.z]);
        self.idx += 1;
        self.x += 1;
        if self.x >= self.w {
            self.x = 0;
            self.y += 1;
            if self.y >= self.h {
                self.y = 0;
                self.z += 1;
            }
        }
        Some(item)
    }
}

/// Row-major cell iteration for a 4D grid: yields `(flat_index, [x, y, z, w])`.
pub fn iter_4d(size: &[usize]) -> Cells4D {
    Cells4D {
        w: size[0],
        h: size[1],
        d: size[2],
        t: size[3],
        x: 0,
        y: 0,
        z: 0,
        w4: 0,
        idx: 0,
    }
}

pub struct Cells4D {
    w: usize,
    h: usize,
    d: usize,
    t: usize,
    x: usize,
    y: usize,
    z: usize,
    w4: usize,
    idx: usize,
}

impl Iterator for Cells4D {
    type Item = (usize, [usize; 4]);

    fn next(&mut self) -> Option<Self::Item> {
        if self.w4 >= self.t {
            return None;
        }
        let item = (self.idx, [self.x, self.y, self.z, self.w4]);
        self.idx += 1;
        self.x += 1;
        if self.x >= self.w {
            self.x = 0;
            self.y += 1;
            if self.y >= self.h {
                self.y = 0;
                self.z += 1;
                if self.z >= self.d {
                    self.z = 0;
                    self.w4 += 1;
                }
            }
        }
        Some(item)
    }
}

/// Converts an integer grid coordinate into the scaled `f64` coordinate used
/// by noise-crate/FastNoiseLite sample positions.
pub fn scaled(coord: usize) -> f64 {
    coord as f64 * COORD_STEP
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_len_maps_1_to_4() {
        assert_eq!(Dim::from_len(1), Some(Dim::D1));
        assert_eq!(Dim::from_len(2), Some(Dim::D2));
        assert_eq!(Dim::from_len(3), Some(Dim::D3));
        assert_eq!(Dim::from_len(4), Some(Dim::D4));
        assert_eq!(Dim::from_len(0), None);
        assert_eq!(Dim::from_len(5), None);
    }

    #[test]
    fn iter_2d_row_major_order() {
        let size = [2usize, 3usize];
        let cells: Vec<(usize, [usize; 2])> = iter_2d(&size).collect();
        assert_eq!(cells.len(), 6);
        assert_eq!(cells[0], (0, [0, 0]));
        assert_eq!(cells[1], (1, [1, 0]));
        assert_eq!(cells[2], (2, [0, 1]));
        assert_eq!(cells[5], (5, [1, 2]));
    }

    #[test]
    fn iter_3d_covers_every_cell_exactly_once() {
        let size = [2usize, 2usize, 2usize];
        let mut seen = vec![false; 8];
        for (idx, _coords) in iter_3d(&size) {
            assert!(!seen[idx], "index {idx} visited twice");
            seen[idx] = true;
        }
        assert!(seen.into_iter().all(|v| v));
    }

    #[test]
    fn iter_4d_covers_every_cell_exactly_once() {
        let size = [2usize, 2usize, 2usize, 2usize];
        let mut seen = vec![false; 16];
        for (idx, _coords) in iter_4d(&size) {
            assert!(!seen[idx], "index {idx} visited twice");
            seen[idx] = true;
        }
        assert!(seen.into_iter().all(|v| v));
    }
}
