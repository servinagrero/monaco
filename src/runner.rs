use crate::job::*;
use std::collections::HashMap;
use std::process::{Command, Stdio};

use handlebars::Handlebars;

use crate::config::{read_dotenv, Config};

/// Resolve a log output
/// Given the global output and the job output, resolve the one to use
/// If the job has not defined
pub fn resolve_log(global: &StepLog, local: &Option<StepLog>) -> StepLog {
    match local {
        Some(output) => output.clone(),
        None => global.clone(),
    }
}

/// The Runner is in charge of running all jobs
#[derive(Debug)]
pub struct Runner<'a> {
    /// Global environment variables
    pub env: HashMap<String, String>,

    /// Global properties
    pub props: HashMap<String, serde_yaml::Value>,

    /// List of jobs to execute
    pub jobs: Vec<Job>,

    /// Template context
    pub ctx: Handlebars<'a>,

    /// Whether to execute the jobs or just print the steps
    pub dry_mode: bool,

    /// Global log output
    pub log: StepLog,
}

impl<'a> Runner<'static> {
    /// Create a new runner from a configuration
    /// A healthcheck of the configuration should be run before.
    pub fn new(config: &'a Config, config_dir: &str) -> Self {
        let props = config.props.clone();
        let mut env = config.env.clone();

        if config.dotenv {
            let dotenv = read_dotenv(config_dir);
            for (name, value) in dotenv.iter() {
                env.insert(name.to_owned(), value.to_string());
            }
        }

        let log = match &config.log {
            Some(output) => output.clone(),
            None => StepLog::ToStdout(true),
        };

        Runner {
            jobs: config.jobs.clone(),
            env,
            props,
            dry_mode: false,
            ctx: Handlebars::new(),
            log,
        }
    }

    /// Get a list of all available job names
    pub fn get_job_names(&self) -> Vec<&str> {
        self.jobs
            .iter()
            .map(|j| j.name.as_str())
            .collect::<Vec<_>>()
    }

    /// Resolve a path
    /// A path is treated as a template
    pub fn resolve_path(&'a self, path: &'a str) -> &str {
        return path;
    }

    /// Interpreter used to execute commands
    /// Defaults to `/bin/sh -c` on linux
    /// Defaults to `cmd /C` on windows
    /// Returns true if the command executed properly and false otherwise
    pub fn run_step(&self, cmd: &str, job: &Job) -> bool {
        let mut cmd_ctx: Command;

        // let data: HashMap<String, Any> = HashMap::new();

        // TODO: Implement the proper template data
        let cmd_body = self
            .ctx
            .render_template(
                &cmd,
                &serde_json::json!({"job": job.name, "props": job.props, "iter": (), "dir": job.dir}),
            )
            .unwrap();

        // TODO: Add option to change shell
        if cfg!(windows) {
            cmd_ctx = Command::new("cmd");
            cmd_ctx.args(vec!["/C", &cmd_body]);
        } else {
            cmd_ctx = Command::new("/bin/sh");
            cmd_ctx.args(vec!["-c", &cmd_body]);
        }

        let output = resolve_log(&self.log, &job.log);
        match output {
            StepLog::ToStdout(is_out) => {
                if !is_out {
                    cmd_ctx.stdout(Stdio::null());
                }
            }
            StepLog::Filepath(out_template) => {
                let out_path = self.resolve_path(&out_template);
                let out_file = std::fs::OpenOptions::new()
                    .append(true)
                    .create(true)
                    .open(out_path)
                    .expect("Could not open log file");
                cmd_ctx.stdout(out_file);
            }
        }

        cmd_ctx.envs(&self.env);
        if let Some(job_env) = &job.env {
            cmd_ctx.envs(job_env);
        }

        if let Some(root) = &job.dir {
            cmd_ctx.current_dir(&root);
        }

        println!("Step => {}", cmd);
        if self.dry_mode {
            return true;
        }

        let child = cmd_ctx.spawn();

        return match child {
            Ok(mut c) => match c.wait() {
                Ok(code) => code.success(),
                Err(_) => false,
            },
            Err(_) => false,
        };
    }

    /// Run all jobs sequentially
    pub fn run_all(&mut self) {
        for job in self.jobs.iter() {
            self.run_job(job);
        }
    }

    /// Get a job from a name
    /// Return None if the job does not exist
    pub fn get_job(&self, name: &str) -> Option<&Job> {
        self.jobs.iter().filter(|&j| j.name == name).next()
    }

    /// Check whether a job should run or not
    /// If the job has conditions, execute them and return true if all of them executed properly
    /// Otherwise, return true if the job has not ben run
    pub fn job_should_run(&self, job: &Job) -> bool {
        if let Some(conds) = &job.when {
            let codes: Vec<bool> = conds.iter().map(|cmd| self.run_step(cmd, &job)).collect();
            return codes.iter().all(|&c| c == true);
        }
        return !job.completed.get();
    }

    ///
    pub fn run_job(&self, job: &Job) -> bool {
        println!("Loading job => {}", job.name);
        if !self.job_should_run(&job) {
            println!("Job has already been executed");
            return true;
        }

        if let Some(depends) = &job.depends {
            for depend in depends.iter() {
                match depend {
                    Step::Command(cmd) => self.run_step(&cmd, &job),
                    Step::Job {
                        job: jobname,
                        props: _,
                    } => self.run_job(self.get_job(jobname).unwrap()),
                };
            }
        }

        if job.steps.is_none() {
            job.completed.set(true);
            return true;
        }

        if let Some(iters) = &job.iters {
            match iters {
                Iter::Inf(_) => println!("Job Inf"),
                Iter::Values(lst) => println!("Job iterations: {lst:?}"),
                Iter::Range { from, to, by } => {
                    println!("Job range: {:?}, {:?}, {:?}", from, to, by)
                }
            }
        };

        // TODO: Executing the templates
        if let Some(templates) = &job.templates {
            for template in templates.iter() {
                let paths: Vec<&str> = template.split(":").collect();
                println!("Input {} => {}", paths[0], paths[1]);
            }
        }

        let job_steps = &job.steps.clone().unwrap();
        for step in job_steps.iter() {
            let exit_ok: bool = match step {
                Step::Command(cmd) => self.run_step(&cmd, &job),
                Step::Job {
                    job: jobname,
                    props: _,
                } => self.run_job(self.get_job(jobname).unwrap()),
            };

            if job.ignore_errors == false && exit_ok == false {
                println!("Step executed with errors");
                job.completed.set(true);
                return exit_ok;
            };
        }

        job.completed.set(true);
        return true;
    }
}
