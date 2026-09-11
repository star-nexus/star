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
