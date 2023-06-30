//! Configure monaco through a file
//!
//! This module provides the [`Config`] struct which is intended to
//! provide a way to configure `Job`s and the `Runner`.
//! This Config should be loaded from a valid file but it can nonetheless
//! be configured directly in the code.

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crate::job::{Iteration, Job, LogOutput, Step};
use crate::utils::{deserialize_file, deserialize_reader};
use serde_json::Value;

/// Config holds all the possible parameters for the runner
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    /// Absolute path to the configuration
    #[serde(default)]
    pub path: String,

    /// Global environment
    #[serde(default)]
    pub env: HashMap<String, String>,

    /// Read the dotenv file (i.e `.env`).
    /// The file is read from the directory where the configuration is placed.
    /// By default it is not read even if the file exists
    #[serde(default)]
    pub dotenv: bool,

    /// Global properties
    #[serde(default)]
    pub props: HashMap<String, Value>,

    /// Global properties loaded from a file
    pub props_file: Option<String>,

    /// Where to write the step output
    pub log: Option<LogOutput>,

    /// Jobs to execute
    #[serde(default)]
    pub jobs: Vec<Job>,
}

impl Config {
    /// Return the absolute path where the configuration is located
    pub fn dir(&self) -> String {
        let parent = std::path::Path::new(&self.path).parent().unwrap();
        String::from(parent.to_str().unwrap())
    }

    /// Create a configuration from a file
    pub fn from_file(path: &str) -> Result<Self> {
        let mut c: Config =
            deserialize_file(path).with_context(|| "Failed to deserialize config")?;

        let config_path = std::fs::canonicalize(path)
            .map_err(|err| eprintln!("Could not get path of config => {}", err))
            .unwrap();
        c.path = config_path.into_os_string().into_string().unwrap();

        if c.dotenv {
            if let Err(e) = c.read_dotenv() {
                return Err(e).context("Problem reading dotenv file");
            }
        }

        if let Some(s) = &c.props_file {
            let props_path = std::fs::canonicalize(s)
                .unwrap()
                .into_os_string()
                .into_string()
                .unwrap();
            match deserialize_file::<HashMap<String, Value>>(&props_path) {
                Ok(map) => {
                    c.props
                        .extend(map.iter().map(|(k, v)| (k.to_string(), v.to_owned())));
                }
                Err(e) => return Err(e).context("Problem reading props file"),
            }
        }

        match c.check() {
            Ok(_) => Ok(c),
            Err(e) => Err(e).context(format!("Failed to read configuration from '{path}'")),
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
                    if let Err(err) = Job::resolve_template(template) {
                        return Err(err)
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

                let deser: Value = serde_json::from_reader(&fp)
                    .with_context(|| "Malformed iters file")
                    .with_context(|| format!("Problem checking job '{}'", job.name))?;

                match deser {
                    Value::Array(_) => (),
                    _ => {
                        bail!("Iterations must be an array")
                    }
                }
            }
            if let Iteration::Range { from, to, by } = &job.iters {
                let step = by.unwrap_or(1);
                let start = from.unwrap_or(0);
                let end = *to;

                if step == 0 {
                    return Err(anyhow::anyhow!("Step cannot be 0"))
                        .with_context(|| format!("Problem checking job '{}'", job.name))?;
                }
                
                if step > 0 && end < start {
                    return Err(anyhow::anyhow!("Range is decreasing but step is positive"))
                        .with_context(|| format!("Problem checking job '{}'", job.name))?;
                }

                if step < 0 && end > start {
                    return Err(anyhow::anyhow!("Range is increasing but step is negative"))
                        .with_context(|| format!("Problem checking job '{}'", job.name))?;
                }
            }

            let mut completed = job.completed.lock().unwrap();
            *completed = false;
        }
        Ok(true)
    }

    /// Read a dotenv file for environment variables
    ///
    /// The dotenv file should be called ".env" but other names can be provided.
    /// Each line in the format is read as `KEY=VALUE`.
    pub fn read_dotenv(&mut self) -> Result<(), anyhow::Error> {
        let env_path: String = Path::new(&self.dir())
            .join(".env")
            .into_os_string()
            .into_string()
            .unwrap();
        let mut env: HashMap<String, String> = HashMap::new();

        return match File::open(&env_path) {
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
                self.env.extend(env);
                Ok(())
            }
            Err(e) => {
                return Err(e)
                    .with_context(|| format!("Problem reading dotenv file at {}", &env_path));
            }
        };
    }
}
