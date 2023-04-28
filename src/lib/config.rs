//! Read configuration for monaco through a file
//!
//! This module provides the [`Config`] struct which is intended to
//! provide a way to configure `Job`s and the `Runner` through a configuration file

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs::File;

use crate::job::{Iteration, Job, LogOutput, Step};
use crate::utils::{deserialize_file, deserialize_reader};

/// Type of Map used by Props
pub(crate) type PropMap = HashMap<String, serde_yaml::Value>;

/// Type of Map used by the Shell environment
pub(crate) type StrMap = HashMap<String, String>;

/// A configuration holds all the possible parameters for the runner
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    /// Absolute path to the configuration
    #[serde(default)]
    pub path: String,

    /// Global environment
    #[serde(default)]
    pub env: StrMap,

    /// Global properties
    #[serde(default)]
    pub props: PropMap,

    /// Global properties
    pub props_file: Option<String>,

    /// Read the dotenv file (i.e `.env`).
    /// The file is read from the directory where the configuration is placed.
    /// By default it is not read even if the file exists
    #[serde(default)]
    pub dotenv: bool,

    /// Where to write the step output
    pub log: Option<LogOutput>,

    /// Jobs to execute
    #[serde(default)]
    pub jobs: Vec<Job>,
}

impl Config {
    /// Create a configuration from a file
    pub fn from_file(path: &str) -> Result<Self> {
        let mut c: Config =
            deserialize_file(path).with_context(|| "Failed to deserialize config")?;

        let config_path = std::fs::canonicalize(path)
            .map_err(|err| eprintln!("Could not get path of config => {}", err))
            .unwrap();
        c.path = config_path.into_os_string().into_string().unwrap();

        match c.check() {
            Ok(_) => Ok(c),
            Err(e) => Err(e).with_context(|| format!("Failed to read configuration from '{path}'")),
        }
    }

    /// Create a configuration from a reader
    ///
    /// The configuration is deserialized using [`deserialize_reader`]
    pub fn from_reader<R: std::io::Read>(reader: &mut R, hint: &str) -> Result<Self> {
        deserialize_reader::<Config>(reader, hint)
    }

    /// Perform a healthcheck for the configuration.
    ///
    /// The following checks are performed on every job:
    /// * The job names are not duplicated.
    /// * The `props_file`, if provided, is readable.
    /// * All jobs, declared or called from another job, exist.
    /// * Template paths are not malformed. See [`Job::resolve_template`]
    /// * The ranges on the iterations are not malformed.
    /// * The completed status is set to false
    pub fn check(&mut self) -> Result<bool> {
        let job_names: Vec<String> = self.jobs.iter().cloned().map(|j| j.name).collect();
        let mut job_set: HashSet<&str> = HashSet::new();

        for name in job_names.iter() {
            job_set.insert(name);
        }

        if job_set.len() != job_names.len() {
            return Err(anyhow::anyhow!("Duplicated job names"))
                .with_context(|| "Problem with the configuration");
        }

        if let Some(s) = &self.props_file {
            if let Err(e) = std::fs::canonicalize(s) {
                return Err(e).with_context(|| format!("Problem reading props file '{s}'"));
            }
        }

        for job in self.jobs.iter_mut() {
            if job.depends.is_none() && job.steps.is_none() {
                return Err(anyhow::anyhow!("No steps or dependencies defined")
                    .context(format!("Problem checking job '{}'", job.name)));
            }

            if let Some(depends) = &job.depends {
                for depend in depends.iter() {
                    if let Step::Job {
                        job: name,
                        props: _,
                        env: _,
                    } = depend
                    {
                        if !job_names.iter().any(|n| n == name) {
                            return Err(anyhow::anyhow!(
                                "Requirement job '{}' does not exist",
                                name
                            )
                            .context(format!("Problem checking job '{}'", job.name)));
                        }
                    }
                }
            }

            if let Some(templates) = &job.templates {
                for template in templates.iter() {
                    if let Err(e) = Job::resolve_template(template) {
                        return Err(e)
                            .context("Template paths are malformed")
                            .context(format!("Problem checking job '{}'", job.name));
                    }
                }
            }

            job.read_props_file()?;

            if let Iteration::File(path) = &job.iters {
                let fp = File::open(&path)
                    .with_context(|| format!("Could not read iteration file {}", path))
                    .with_context(|| format!("Problem checking job '{}'", job.name))?;

                let deser: serde_json::Value = serde_json::from_reader(&fp)
                    .with_context(|| "Malformed iters file")
                    .with_context(|| format!("Problem checking job '{}'", job.name))?;

                match deser {
                    serde_json::Value::Array(_) => (),
                    _ => {
                        bail!("Iterations must be an array")
                    }
                }
            }
            let mut completed = job.completed.lock().unwrap();
            *completed = false;
        }
        Ok(true)
    }
}
