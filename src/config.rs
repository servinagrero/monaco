use std::collections::HashMap;
use std::error::Error;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::process::exit;

use serde::{Deserialize, Serialize};

use crate::job::*;

#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    /// Global environment
    #[serde(default)]
    pub env: HashMap<String, String>,

    /// Global properties
    #[serde(default)]
    pub props: HashMap<String, serde_yaml::Value>,

    /// Wether to parse .env file
    #[serde(default)]
    pub dotenv: bool,

    /// Filepath to the secrets file
    pub secrets: Option<String>,

    /// Where to write the step output
    pub log: Option<StepLog>,

    /// Jobs to execute
    #[serde(default)]
    // jobs: HashMap<String, Job>,
    pub jobs: Vec<Job>,
}

impl Config {
    /// Create a configuration from a file
    pub fn from_file(path: &str) -> Result<Self, Box<dyn Error>> {
        // let config_path = match fs::canonicalize(&path)
        match File::open(path) {
            Ok(fp) => {
                let hint = Path::new(path).extension().unwrap();
                let mut reader = BufReader::new(fp);
                return Config::from_reader(&mut reader, hint.to_str().unwrap());
            }
            Err(e) => return Err(Box::new(e)),
        }
    }

    /// Create a configuration from a reader
    pub fn from_reader<R: std::io::Read>(
        reader: &mut R,
        hint: &str,
    ) -> Result<Self, Box<dyn Error>> {
        return match hint {
            "yml" | "yaml" => match serde_yaml::from_reader(reader) {
                Ok(c) => Ok(c),
                Err(e) => Err(Box::new(e)),
            },
            "toml" => {
                let content = std::io::read_to_string(reader).unwrap();
                match toml::from_str(&content) {
                    Ok(c) => Ok(c),
                    Err(e) => Err(Box::new(e)),
                }
            }
            "json" => match serde_json::from_reader(reader) {
                Ok(c) => Ok(c),
                Err(e) => Err(Box::new(e)),
            },
            _ => {
                println!("File format '{}' is not supported", hint);
                println!("Available formats => yml, yaml, toml, json");
                exit(1);
            }
        };
    }

    /// Perform a healthcheck for the configuration.
    /// The following checks are performed on every job in order:
    ///
    /// * The job dependencies exist.
    /// * Template paths are not malformed.
    /// * The ranges on the iterations are not malformed.
    pub fn check(&self) -> bool {
        let job_names: Vec<&str> = self.jobs.iter().map(|j| &*j.name).collect();

        for job in self.jobs.iter() {
            if let Some(depends) = &job.depends {
                for depend in depends.iter() {
                    if let Step::Job {
                        job: name,
                        props: _,
                    } = depend
                    {
                        if !job_names.iter().any(|n| n == name) {
                            println!("Problem in job '{}'", job.name);
                            println!("Requerement job '{}' does not exist", name);
                            println!("Possible jobs are => {:?}", job_names.join(", "));
                            return false;
                        }
                    }
                }
            }
            if let Some(templates) = &job.templates {
                for template in templates.iter() {
                    let paths: Vec<&str> = template.split(":").collect();
                    if paths.len() != 2 {
                        println!("Problem in job '{}'", job.name);
                        println!("Template paths are malformed: {}", template);
                        return false;
                    }
                }
            }
            // if let Some(iters) = &job.iters {
            //     if let Iter::Range { from, to: _, by: _ } = iters {
            //         if from.is_none() {
            //             println!("Problem in job '{}'", job.name);
            //             println!("Range wasn't specified");
            //             return false;
            //         }
            //     }
            // }
            job.completed.set(false);
        }

        return true;
    }
}

/// Read a dotenv file for environment variables
/// The file ".env" is read from the specified directory
/// The lines should have the format `KEY=VALUE`
pub fn read_dotenv(dir: &str) -> HashMap<String, String> {
    let mut env = HashMap::<String, String>::new();

    let env_path = Path::new(dir).join(".env");
    match File::open(&env_path) {
        Ok(fp) => {
            let reader = BufReader::new(fp);
            for (line_id, line) in reader.lines().enumerate() {
                let line = line.unwrap();
                if line == "" {
                    continue;
                };
                match line.split_once("=") {
                    Some((key, value)) => {
                        env.insert(key.to_string(), value.to_string());
                    }
                    None => println!("Malformed line {} in .env => {line}", line_id + 1),
                }
            }
        }
        Err(e) => {
            println!("Could not read {} => {e}", env_path.to_string_lossy());
        }
    }
    return env;
}
