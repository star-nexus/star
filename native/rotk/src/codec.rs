//! Owned diagnostic encoding for Python sets and non-string-key dictionaries.
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    ops::{Deref, DerefMut},
};

/// CPython truth value for JSON-shaped action parameters.
pub fn truthy(value: &serde_json::Value) -> bool {
    use serde_json::Value;
    match value {
        Value::Null => false,
        Value::Bool(v) => *v,
        Value::Number(v) => v.as_f64() != Some(0.),
        Value::String(v) => !v.is_empty(),
        Value::Array(v) => !v.is_empty(),
        Value::Object(v) => !v.is_empty(),
    }
}

/// Legacy action handlers accept bool as int (the observation unit_ids list does not).
pub fn action_integer(value: &serde_json::Value) -> Option<i128> {
    value
        .as_i64()
        .map(i128::from)
        .or_else(|| value.as_u64().map(i128::from))
        .or_else(|| value.as_bool().map(i128::from))
}
pub fn string_repr(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::new();
    out.push(quote);
    for c in text.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if c.is_ascii_control() => out.push_str(&format!("\\x{:02x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}
pub fn scalar_display(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::String(v) => v.clone(),
        serde_json::Value::Bool(true) => "True".into(),
        serde_json::Value::Bool(false) => "False".into(),
        serde_json::Value::Null => "None".into(),
        other => other.to_string(),
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct TaggedSet<T: Ord>(pub BTreeSet<T>);
impl<T: Ord> Deref for TaggedSet<T> {
    type Target = BTreeSet<T>;
    fn deref(&self) -> &Self::Target {
        &self.0
    }
}
impl<T: Ord> DerefMut for TaggedSet<T> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.0
    }
}
impl<T: Ord + Serialize> Serialize for TaggedSet<T> {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut values: Vec<_> = self.0.iter().collect();
        values.sort_by_cached_key(|p| serde_json::to_string(p).unwrap());
        serde_json::json!({"$set":values}).serialize(s)
    }
}
impl<'de, T: Ord + Deserialize<'de>> Deserialize<'de> for TaggedSet<T> {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields, bound(deserialize = "T: Deserialize<'de>"))]
        struct Tagged<T> {
            #[serde(rename = "$set")]
            values: Vec<T>,
        }
        let values = Tagged::deserialize(d)?.values;
        let length = values.len();
        let result: BTreeSet<T> = values.into_iter().collect();
        if result.len() != length {
            return Err(serde::de::Error::custom("duplicate set member"));
        }
        Ok(Self(result))
    }
}

pub mod id_map {
    use super::*;
    pub fn serialize<T: Serialize, S: serde::Serializer>(
        map: &BTreeMap<u64, T>,
        s: S,
    ) -> Result<S::Ok, S::Error> {
        if map.is_empty() {
            return serde_json::json!({}).serialize(s);
        }
        let mut pairs: Vec<_> = map.iter().collect();
        pairs.sort_by_cached_key(|(id, _)| id.to_string());
        serde_json::json!({"$map":pairs}).serialize(s)
    }
    pub fn deserialize<'de, T: Deserialize<'de>, D: serde::Deserializer<'de>>(
        d: D,
    ) -> Result<BTreeMap<u64, T>, D::Error> {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields, bound(deserialize = "T: Deserialize<'de>"))]
        struct Tagged<T> {
            #[serde(rename = "$map", default)]
            pairs: Vec<(u64, T)>,
        }
        let entries = Tagged::deserialize(d)?.pairs;
        let count = entries.len();
        let result: BTreeMap<_, _> = entries.into_iter().collect();
        if result.len() != count {
            return Err(serde::de::Error::custom("duplicate ID map key"));
        }
        Ok(result)
    }
}
