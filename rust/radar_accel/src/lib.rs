//! radar_accel — High-performance earthquake data parsing and filtering.
//!
//! This Rust extension module provides fast JSON parsing of USGS GeoJSON
//! feeds and efficient event filtering. Exposed to Python via PyO3.
//!
//! Build with: `cd rust/radar_accel && maturin develop`

use pyo3::prelude::*;
use serde::Deserialize;
use std::collections::HashSet;

// ── GeoJSON structures ────────────────────────────────────────

#[derive(Deserialize)]
struct GeoJsonFeed {
    features: Vec<Feature>,
}

#[derive(Deserialize)]
struct Feature {
    id: String,
    properties: Properties,
    geometry: Geometry,
}

#[derive(Deserialize)]
struct Properties {
    mag: Option<f64>,
    place: Option<String>,
    time: Option<i64>,
    #[serde(rename = "magType")]
    mag_type: Option<String>,
    felt: Option<i64>,
    tsunami: Option<i64>,
    url: Option<String>,
}

#[derive(Deserialize)]
struct Geometry {
    coordinates: Vec<f64>, // [lon, lat, depth]
}

// ── Python-facing structures ──────────────────────────────────

#[pyclass]
#[derive(Clone)]
struct QuakeEvent {
    #[pyo3(get)]
    id: String,
    #[pyo3(get)]
    magnitude: f64,
    #[pyo3(get)]
    depth: f64,
    #[pyo3(get)]
    place: String,
    #[pyo3(get)]
    time_ms: i64,
    #[pyo3(get)]
    latitude: f64,
    #[pyo3(get)]
    longitude: f64,
    #[pyo3(get)]
    url: String,
    #[pyo3(get)]
    felt: Option<i64>,
    #[pyo3(get)]
    tsunami: bool,
    #[pyo3(get)]
    mag_type: String,
}

// ── Module functions ──────────────────────────────────────────

/// Parse a raw GeoJSON string into a list of QuakeEvent objects.
///
/// This is significantly faster than Python's json.loads() + manual
/// field extraction for large feeds (1000+ events).
#[pyfunction]
fn parse_geojson(raw: &str) -> PyResult<Vec<QuakeEvent>> {
    let feed: GeoJsonFeed = serde_json::from_str(raw)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("JSON parse error: {}", e)))?;

    let events: Vec<QuakeEvent> = feed
        .features
        .into_iter()
        .filter_map(|feat| {
            let coords = &feat.geometry.coordinates;
            if coords.len() < 2 {
                return None;
            }

            Some(QuakeEvent {
                id: feat.id,
                magnitude: feat.properties.mag.unwrap_or(0.0),
                depth: coords.get(2).copied().unwrap_or(0.0),
                place: feat.properties.place.unwrap_or_else(|| "Unknown".to_string()),
                time_ms: feat.properties.time.unwrap_or(0),
                latitude: coords[1],
                longitude: coords[0],
                url: feat.properties.url.unwrap_or_default(),
                felt: feat.properties.felt,
                tsunami: feat.properties.tsunami.map_or(false, |t| t != 0),
                mag_type: feat.properties.mag_type.unwrap_or_default(),
            })
        })
        .collect();

    Ok(events)
}

/// Filter events by minimum magnitude threshold.
#[pyfunction]
fn filter_by_magnitude(events: Vec<QuakeEvent>, min_mag: f64) -> Vec<QuakeEvent> {
    events
        .into_iter()
        .filter(|e| e.magnitude >= min_mag)
        .collect()
}

/// Compute the diff between two sets of event IDs.
///
/// Returns a tuple of (added_ids, removed_ids).
#[pyfunction]
fn diff_event_ids(
    old_ids: Vec<String>,
    new_ids: Vec<String>,
) -> (Vec<String>, Vec<String>) {
    let old_set: HashSet<String> = old_ids.into_iter().collect();
    let new_set: HashSet<String> = new_ids.into_iter().collect();

    let added: Vec<String> = new_set.difference(&old_set).cloned().collect();
    let removed: Vec<String> = old_set.difference(&new_set).cloned().collect();

    (added, removed)
}

// ── Module registration ───────────────────────────────────────

#[pymodule]
fn radar_accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_geojson, m)?)?;
    m.add_function(wrap_pyfunction!(filter_by_magnitude, m)?)?;
    m.add_function(wrap_pyfunction!(diff_event_ids, m)?)?;
    m.add_class::<QuakeEvent>()?;
    Ok(())
}
