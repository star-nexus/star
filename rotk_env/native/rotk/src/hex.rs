//! Exact offset-hex conventions and deterministic ties from the R0 oracle.
pub type Hex = (i64, i64);

pub fn axial((col, row): Hex) -> Hex {
    (col, row - (col - (col & 1)) / 2)
}
pub fn offset((q, r): Hex) -> Hex {
    (q, r + (q - (q & 1)) / 2)
}
pub fn distance(a: Hex, b: Hex) -> i64 {
    let (q, r) = axial(a);
    let (s, t) = axial(b);
    ((q - s).abs() + (r - t).abs() + ((-q - r) - (-s - t)).abs()) / 2
}
pub fn neighbors((col, row): Hex) -> [Hex; 6] {
    let shifts = if col & 1 == 0 {
        [(1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1), (1, 0)]
    } else {
        [(1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1), (1, 1)]
    };
    shifts.map(|(c, r)| (col + c, row + r))
}
pub fn line(a: Hex, b: Hex) -> Vec<Hex> {
    let (q1, r1) = axial(a);
    let (q2, r2) = axial(b);
    let d = distance(a, b);
    if d == 0 {
        return vec![a];
    }
    (0..=d)
        .map(|i| {
            let t = i as f64 / d as f64;
            offset((
                (q1 as f64 + (q2 - q1) as f64 * t).round_ties_even() as i64,
                (r1 as f64 + (r2 - r1) as f64 * t).round_ties_even() as i64,
            ))
        })
        .collect()
}
pub fn repr((c, r): Hex) -> String {
    format!("({c}, {r})")
}
pub fn repr_list(cells: &[Hex]) -> String {
    format!(
        "[{}]",
        cells
            .iter()
            .map(|&p| repr(p))
            .collect::<Vec<_>>()
            .join(", ")
    )
}
