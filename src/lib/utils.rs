//! Utilities for monaco

use anyhow::{Context, Result};
use serde::de::DeserializeOwned;
use std::collections::HashMap;
use std::fs::File;
use std::io::BufReader;

// Merge two hashmaps into a single hashmap
pub fn merge_maps(
    first: &HashMap<String, serde_json::Value>,
    second: &HashMap<String, serde_json::Value>,
) -> HashMap<String, String> {
    let to_str = |v: &serde_json::Value| serde_json::to_string(v).unwrap_or_default();

    first
        .into_iter()
        .chain(second)
        .map(|(k, v)| (k.clone(), to_str(v)))
        .collect::<HashMap<_, _>>()
}

/// Deserialize from a reader into an instance of type T
///
/// The extension should be provided in lowercase
pub fn deserialize_reader<'a, T>(reader: impl std::io::Read, ext: &str) -> Result<T>
where
    T: DeserializeOwned,
{
    return match ext {
        "json" => match serde_json::from_reader(reader) {
            Ok(object) => Ok(object),
            Err(e) => Err(anyhow::anyhow!(e)),
        },
        "toml" => {
            let txt = std::io::read_to_string(reader).unwrap();
            match toml::from_str(&txt) {
                Ok(object) => Ok(object),
                Err(e) => Err(anyhow::anyhow!(e)),
            }
        }
        "yml" | "yaml" => match serde_yaml::from_reader(reader) {
            Ok(object) => Ok(object),
            Err(e) => Err(anyhow::anyhow!(e)),
        },
        _ => Err(anyhow::anyhow!("Format not supported")),
    };
}

/// Deserialize a file into an instance of type T
///
/// In order to extend this functionality to allow users to
/// add their own extensions and deserializers create a struct
/// with a map containing extensions and the corresponding functions
pub fn deserialize_file<'a, T>(path: &str) -> Result<T>
where
    T: DeserializeOwned,
{
    let fp = File::open(&path).with_context(|| format!("Failed to read file {}", path))?;
    let reader = BufReader::new(fp);
    let ext = std::path::Path::new(path)
        .extension()
        .unwrap()
        .to_ascii_lowercase()
        .into_string()
        .unwrap();
    return deserialize_reader(reader, &ext);
}
