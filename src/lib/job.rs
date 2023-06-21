//! Define the set of steps to run

use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};

use crate::config::{PropMap, StrMap};
use crate::utils::deserialize_file;

/// Iterations for the steps
/// By default, the steps are executed once
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Iteration {
    /// Path to a JSON file containing an array of values
    File(String),

    /// Whether the job should be executed in a loop
    /// True for an infinite loop and false for a single iteration
    Loop(bool),

    /// Range of values.
    /// The range works like a for loop.
    /// By default starts at 0. If step is not specified, it defaults to 1
    Range {
        from: Option<u64>,
        to: u64,
        by: Option<u64>,
    },

    /// List of values
    /// TODO: Make it generic and don't depend on yaml
    Values(Vec<serde_yaml::Value>),
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
    ///
    /// The path is recalculated every iteration.
    Filepath(String),
}

impl std::default::Default for LogOutput {
    fn default() -> Self {
        LogOutput::ToStdout(true)
    }
}

/// Steps that a job can execute.
/// A job can execute either a shell command or another job
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
        props: Option<PropMap>,
        env: Option<StrMap>,
    },
}

/// A job defines the steps to run plus their configuration
///
///
/// Templates are defined similar to docker, that is `/path/to/input:/path/to/output`.
///
/// Both input and output paths are treated as templates so we can extrapolate variables.
/// `/path/to/input_{{iter}}:/path/to/output_{{iter}}`
#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct Job {
    /// Descriptive name of the Job
    pub name: String,

    /// If provided, treat this as the root directory
    /// The path is automatically converted to an absolute path
    pub dir: Option<String>,

    /// Environment variables
    #[serde(default)]
    pub env: StrMap,

    /// Properties of the job
    #[serde(default)]
    pub props: PropMap,

    /// Path to a file containing props
    pub props_file: Option<String>,

    /// Steps to execute. Steps are executed in the order they are defined
    pub steps: Option<Vec<Step>>,

    /// Iterations to execute
    #[serde(default)]
    pub iters: Iteration,

    /// List of dependencies that will be run once
    pub depends: Option<Vec<Step>>,

    /// Templates to execute.
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
    pub message: Option<String>,
}

impl Job {
    /// Read props from the provided `props_file`
    /// If no `props_file` is provided, do nothing
    /// The file is deserialized with the [`deserialize_file`] function
    pub fn read_props_file(&mut self) -> Result<bool> {
        if let Some(path) = &self.props_file {
            match deserialize_file::<PropMap>(path) {
                Ok(props) => {
                    self.props.extend(props);
                    return Ok(true);
                }
                Err(e) => bail!(e),
            };
        };
        Ok(true)
    }

    /// Resolve a raw template path into a pair of paths
    pub fn resolve_template(template: &str) -> Result<(&str, &str)> {
        let paths: Vec<&str> = template.split(":").collect();
        return match paths.len() {
            1 => {
                bail!("No path was provided. Use ':' to split the input and output path.")
            }
            2 => {
                if paths[0].is_empty() {
                    bail!("Input path should not be empty.")
                } else if paths[1].is_empty() {
                    bail!("Output path should not be empty.")
                } else {
                    Ok((paths[0], paths[1]))
                }
            }
            _ => bail!("More than 2 paths detected."),
        };
    }
}
