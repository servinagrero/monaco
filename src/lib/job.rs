//! Define the set of steps to run

use crate::utils::deserialize_file;
use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

/// Iterations for the steps
/// By default, the steps are executed once
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Iteration {
    /// Path to a JSON file containing an array of values
    File(String),

    /// Whether the job should be executed in an infinite loop
    /// or in a single iteration
    // TODO: How to handle infinite loop in [`resolve_iters`]
    Loop(bool),

    /// Range of values.
    /// The range works like a for loop.
    /// By default starts at 0. If step is not specified, it defaults to 1
    Range {
        from: Option<i64>,
        to: i64,
        by: Option<i64>,
    },

    /// List of values
    Values(Vec<serde_json::Value>),
}

impl std::default::Default for Iteration {
    fn default() -> Self {
        Iteration::Loop(false)
    }
}

/// Type of execution for the iterations.
///
/// By default jobs run sequentially
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ExecutionType {
    /// Run each iteration in parallel or sequentially.
    /// If running in parallel, use the maximum number of threads available.
    Parallel(bool),

    /// Run the iterations in parallel with the specific number of threads
    WithThreads(i32),
}

impl std::default::Default for ExecutionType {
    fn default() -> Self {
        ExecutionType::Parallel(false)
    }
}

/// Where to log the output of each step
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum LogOutput {
    /// Output to standard output. If False, no output is emitted.
    ToStdout(bool),

    /// Template for an absolute path.
    /// The path is recalculated every iteration.
    Filepath(String),
}

impl std::default::Default for LogOutput {
    fn default() -> Self {
        LogOutput::ToStdout(true)
    }
}

/// Steps that a job can execute.
/// A job can execute shell commands or other jobs
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Step {
    /// The command is directly a string template.
    Command(String),

    /// The command is another job.
    ///
    /// The props and env of the job can be changed
    #[serde(rename(deserialize = "job"))]
    Job {
        job: String,
        props: Option<HashMap<String, Value>>,
        env: Option<HashMap<String, String>>,
    },
}

/// A job defines the steps to run plus their configuration
///
///
/// Templates are defined similar to docker, that is `/path/to/input:/path/to/output`.
/// Both input and output paths are treated as templates so we can extrapolate variables.
///
/// ```
/// /path/to/input_{{iter}}:/path/to/output_{{iter}}
/// ```
///
/// This is important as the paths are read as absolute paths, even if the execution
/// directory is provided. In that case, prepend the variable `{{dir}}` to the path:
///
/// ```
/// {{dir}}/input:{{dir}}output
/// ```
#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct Job {
    /// Descriptive name of the Job
    pub name: String,

    /// If provided, treat this as the root directory
    /// The path is automatically converted to an absolute path
    pub dir: Option<String>,

    /// Environment variables
    #[serde(default)]
    pub env: HashMap<String, String>,

    /// Properties of the job
    #[serde(default)]
    pub props: HashMap<String, Value>,

    /// Path to a file containing props
    pub props_file: Option<String>,

    /// Steps to execute. Steps are executed in the order they are defined
    pub steps: Option<Vec<Step>>,

    /// Iterations to execute
    #[serde(default)]
    pub iters: Iteration,

    /// List of dependencies that will be run once before executing the steps
    pub depends: Option<Vec<Step>>,

    /// Templates to execute
    pub templates: Option<Vec<String>>,

    /// Run the steps in parallel or sequentially
    #[serde(default)]
    pub parallel: ExecutionType,

    /// Ignore errors when executing steps
    #[serde(default)]
    pub ignore_errors: bool,

    /// Where to output each job
    /// If no output is provided, default to the runner's output
    pub log: Option<LogOutput>,

    /// List of conditions to check if the job should be executed
    /// If no conditions are specified, use the `completed` field
    pub when: Option<Vec<String>>,

    /// The job was already completed and shouldn't be executed again
    #[serde(skip)]
    pub completed: Arc<Mutex<bool>>,

    /// Message to print when executing a job
    /// The message is printed to stdout at the beginning of every iterationg
    pub message: Option<String>,
}

impl Job {
    /// Read props from the provided `props_file`
    /// If no `props_file` is provided, do nothing
    /// The file is deserialized with the [`deserialize_file`] function
    pub fn read_props_file(&mut self) -> Result<(), anyhow::Error> {
        if let Some(path) = &self.props_file {
            match deserialize_file::<HashMap<String, serde_json::Value>>(path) {
                Ok(props) => {
                    self.props.extend(props);
                    return Ok(());
                }
                Err(e) => bail!(e),
            };
        };
        Ok(())
    }

    /// Given a path template, provide input and output paths
    /// If the template is illformed, return an error
    pub fn resolve_template(template: &str) -> Result<(String, String)> {
        let parts: Vec<&str> = template.split(":").filter(|p| *p != "").collect();
        match parts.len() {
            1 => {
                bail!("Template must have both input and output path");
            }
            2 => {
                return Ok((parts[0].to_string(), parts[1].to_string()));
            }
            _ => {
                bail!("Template should only have input and output path");
            }
        }
    }

    pub fn resolve_iters(&self) -> Vec<serde_json::Value> {
        match &self.iters {
            Iteration::Values(vals) => {
                return vals
                    .iter()
                    .map(|i| serde_json::to_value(i).unwrap())
                    .collect::<Vec<serde_json::Value>>();
            }
            Iteration::Range { from, to: end, by } => {
                let mut res: Vec<serde_json::Value> = Vec::new();
                let start = from.unwrap_or(0);
                let step = by.unwrap_or(1);
                let mut counter = start;
                while counter < *end {
                    counter += step;
                    res.push(serde_json::to_value(counter).unwrap())
                }
                return res;
            }
            Iteration::File(file) => Vec::new(),
            Iteration::Loop(is_loop) => Vec::new(),
            _ => Vec::new(),
        }
    }
}
