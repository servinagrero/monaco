use serde::{Deserialize, Serialize};
use std::cell::Cell;
use std::collections::HashMap;

/// Iterations for the steps
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Iter {
    /// A range of values. By default starts at 0
    Range {
        from: Option<u64>,
        to: Option<u64>,
        by: Option<u64>,
    },
    /// List of values
    Values(Vec<serde_yaml::Value>),
}

/// Where to log the output of
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum StepLog {
    /// True for stdout
    /// False for no output
    ToStdout(bool),

    /// Template for a path that is calculated in each iteration
    Filepath(String),
}

impl Default for StepLog {
    fn default() -> Self {
        StepLog::ToStdout(true)
    }
}

/// Steps that a job can execute. It can execute:
/// - A shell command
/// - Another job
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Step {
    /// The command is directly a string template
    Command(String),

    /// The command is another job
    #[serde(rename(deserialize = "job"))]
    Job {
        job: String,
        props: Option<HashMap<String, String>>,
    },
}

/// Jobs are executed in the order they are on the config file
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    /// Descriptive name of the Job
    pub name: String,

    /// Change directory for the job
    pub dir: Option<String>,

    /// Environment variables
    pub env: Option<HashMap<String, String>>,

    /// Properties of the job
    pub props: Option<HashMap<String, serde_yaml::Value>>,

    /// List of secret files
    pub secrets: Option<Vec<String>>,

    /// Steps to execute. Steps are also executed in order
    pub steps: Option<Vec<Step>>,

    /// Iterations to execute
    pub iters: Option<Iter>,

    /// List of dependencies that will be run once
    pub depends: Option<Vec<Step>>,

    /// List of conditions to check if the job should be executed
    pub when: Option<Vec<String>>,

    // Templates to executeP
    pub templates: Option<Vec<String>>,

    /// Whether to ignore errors
    #[serde(default)]
    pub ignore_errors: bool,

    // Output of the job
    pub log: Option<StepLog>,

    // Whether the job was completed
    #[serde(default)]
    pub completed: Cell<bool>,
}
