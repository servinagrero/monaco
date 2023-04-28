//! Utilities for monaco

use anyhow::{Context, Result};
use serde::de::DeserializeOwned;
use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader};

use crate::config::{PropMap, StrMap};

/// Read a dotenv file for environment variables
///
/// The dotenv file should be called ".env" but other names can be provided.
/// Each line in the format is read as `KEY=VALUE`.
pub fn read_dotenv<T: AsRef<str>>(env_path: T) -> Result<StrMap> {
    let mut env = StrMap::new();

    return match File::open(env_path.as_ref()) {
        Ok(fp) => {
            let reader = BufReader::new(fp);
            for (line_id, line) in reader
                .lines()
                .filter(|l| l.as_ref().unwrap() != "")
                .enumerate()
            {
                let line = line.unwrap();

                line.split_once("=")
                    .map(|(key, value)| env.insert(key.to_string(), value.to_string()))
                    .with_context(|| {
                        format!("Malformed line {} in dotenv => {line}", line_id + 1)
                    })?;
            }
            Ok(env)
        }
        Err(e) => {
            return Err(e)
                .with_context(|| format!("Problem reading dotenv file at {}", env_path.as_ref()));
        }
    };
}

/// Convert a HashMap into a HashMap<String, String>
#[macro_export]
macro_rules! map_to_str {
    ($e:expr) => {
        $e.iter()
            .map(|(k, v)| {
                let deser: String = serde_yaml::to_string(v).unwrap_or_default();
                (k.clone(), String::from(deser.trim_end().replace("'", "")))
            })
            .collect::<HashMap<String, String>>()
    };
}

// Merge two hashmaps into a single hashmap
pub fn merge_maps(first: &PropMap, second: &PropMap) -> StrMap {
    let mut map: StrMap = HashMap::new();
    let _ = &[first, second]
        .to_vec()
        .iter()
        .map(|m| map.extend(map_to_str!(m)));
    return map;
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
