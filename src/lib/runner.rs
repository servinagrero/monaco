//! Run the jobs

use crate::job::*;
use anyhow::Result;
use serde::Serialize;
use serde_json::Value;
use std::collections::HashMap;
use std::process::{Command, Stdio};

use handlebars::Handlebars;

use crate::config::Config;
use crate::job::Iteration;
use crate::utils::*;

#[derive(Debug, Default, Serialize, Clone)]
pub struct TemplateData {
    /// Current job
    pub job: String,

    /// Directory where the config is read from
    pub config_dir: String,

    /// Directory of execution
    pub dir: Option<String>,

    /// Current iteration
    pub iter: Option<Value>,

    /// If executing in parallel, the thread index
    /// If executing sequentially, default to 0
    pub thread: i32,

    /// Shell environment
    pub env: HashMap<String, String>,

    /// Properties
    pub props: HashMap<String, Value>,
}

/// The Runner is in charge of running all jobs
#[derive(Debug)]
pub struct Runner<'a> {
    /// Global environment variables
    pub env: HashMap<String, String>,

    /// Global properties
    pub props: HashMap<String, Value>,

    /// List of jobs to execute
    pub jobs: Vec<Job>,

    /// Template context
    pub ctx: Handlebars<'a>,

    /// Whether to execute the jobs or just print the steps
    pub dry_mode: bool,

    /// Global log output
    pub log: LogOutput,

    /// Directory where the configuration is read from
    pub config_dir: String,
}

impl<'a> Runner<'static> {
    /// Create a new runner from a configuration
    /// A healthcheck of the configuration should be run before.
    pub fn from_config(config: &'a Config) -> Result<Self> {
        let log = match &config.log {
            Some(output) => output.clone(),
            None => LogOutput::default(),
        };

        Ok(Runner {
            jobs: config.jobs.clone(),
            config_dir: config.dir(),
            env: config.env.clone(),
            props: config.props.clone(),
            dry_mode: false,
            ctx: Handlebars::new(),
            log,
        })
    }

    /// Render a template
    ///
    /// Automatically creates directories for the output path
    pub fn render_template(
        &self,
        input_path: &str,
        output_path: &str,
        data: &TemplateData,
    ) -> Result<()> {
        let resolve_path = |path| self.ctx.render_template(path, &data).unwrap();
        let input_path = resolve_path(input_path);
        let output_path = resolve_path(output_path);

        let input_str = std::fs::read_to_string(&input_path)?;

        let path = std::path::Path::new(&output_path);
        let prefix = path.parent().unwrap();
        std::fs::create_dir_all(prefix)?;

        let fp = std::fs::File::create(&output_path)?;

        println!("Executing template {} => {}", input_path, output_path);
        self.ctx.render_template_to_write(&input_str, &data, fp)?;
        Ok(())
    }

    /// Execute a single shell command.
    ///
    /// On linux, the command is executed as `/bin/sh -c command`.
    /// On window, the command is executed as `cmd /C command`.
    /// If there were no errors during execution, return true if the command succeded.
    /// If errors were encountered or the command didn't succed, returns false.
    pub fn exec_command(&self, cmd: &str, data: &TemplateData, log: &Option<LogOutput>) -> bool {
        let mut cmd_ctx: Command;

        let result = self.ctx.render_template(&cmd, &data);
        let cmd_body = match result {
            Ok(body) => body,
            Err(e) => {
                println!("Error generating command: {}", e);
                return false;
            }
        };

        // TODO: Add option to change shell
        if cfg!(windows) {
            cmd_ctx = Command::new("cmd");
            cmd_ctx.args(vec!["/C", &cmd_body]);
        } else {
            cmd_ctx = Command::new("/bin/sh");
            cmd_ctx.args(vec!["-c", &cmd_body]);
        }

        let output = match log {
            Some(l) => &l,
            None => &self.log,
        };

        match output {
            LogOutput::ToStdout(is_out) if !is_out => {
                cmd_ctx.stdout(Stdio::null());
            }
            LogOutput::Filepath(out_template) => {
                let out_path = self.ctx.render_template(&out_template, &data).unwrap();
                let out_file = std::fs::OpenOptions::new()
                    .append(true)
                    .create(true)
                    .open(out_path)
                    .expect("Could not open log file");
                cmd_ctx.stdout(out_file);
            }
            _ => (),
        }

        cmd_ctx.envs(&data.env);

        if let Some(root) = &data.dir {
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

    /// Get a job from a name
    /// Return None if the job does not exist
    pub fn get_job<T: AsRef<str>>(&self, name: T) -> Option<&Job> {
        self.jobs.iter().filter(|&j| j.name == name.as_ref()).next()
    }

    /// Check whether a job should run or not
    ///
    /// If the job has conditions, execute them and return true if all of them executed properly
    /// Otherwise, return true if the job has not ben run
    pub fn job_should_run(&self, job: &Job, data: &TemplateData) -> bool {
        if let Some(conds) = &job.when {
            // return conds
            //     .iter()
            //     .map(|cmd| self.exec_command(cmd, &data, &job.log))
            //     .all(|c| c == true);

            let res: Vec<bool> = conds
                .iter()
                .map(|cmd| self.exec_command(cmd, &data, &job.log))
                .collect();
            println!("{:?}", res);
            return res.iter().all(|c| *c == true);
        }
        let completed = job.completed.lock().unwrap();
        return !*completed;
    }

    pub fn run_steps(&'a self, job: &Job, data: &mut TemplateData) -> bool {
        let job_steps = &job.steps.clone().unwrap();
        for step in job_steps.iter() {
            let exit_ok: bool = match step {
                Step::Command(cmd) => self.exec_command(&cmd, &data, &job.log),
                Step::Job {
                    job: jobname,
                    props,
                    env,
                } => {
                    let mut inner_data = data.clone();
                    if let Some(p) = props {
                        inner_data.props.extend(p.clone());
                    }
                    if let Some(e) = env {
                        inner_data.env.extend(e.clone());
                    }
                    self.run_job(self.get_job(jobname).unwrap(), Some(&mut inner_data))
                }
            };

            if job.ignore_errors == false && exit_ok == false {
                println!("Step executed with errors");
                let mut completed = job.completed.lock().unwrap();
                *completed = true;
                return exit_ok;
            };
        }
        return true;
    }

    pub fn exec_templates(&'a self, templates: &'a Vec<String>, data: &TemplateData) -> bool {
        for template in templates.iter() {
            let (in_path, out_path) = Job::resolve_template(template).unwrap();
            let status = self.render_template(&in_path, &out_path, &data);
            if status.is_err() {
                println!("{:#?}", status);
                return false;
            }
        }
        return true;
    }

    /// Run a single job
    pub fn run_job(&'a self, job: &'a Job, template_data: Option<&mut TemplateData>) -> bool {
        let mut default_data = TemplateData::default();

        let mut data = match template_data {
            Some(d) => d,
            None => {
                default_data.props.extend(self.props.clone());
                default_data.env.extend(self.env.clone());
                default_data.env.extend(job.env.clone());
                default_data.props.extend(job.props.clone());
                &mut default_data
            }
        };
        data.config_dir = self.config_dir.to_string();
        data.job = job.name.clone();

        if let Some(dir) = &job.dir {
            data.dir = Some(dir.to_string());
        }

        println!("Loading job => {}", job.name);

        if !self.job_should_run(&job, &data) {
            println!("Job has already been executed");
            return true;
        }

        if let Some(depends) = &job.depends {
            for depend in depends.iter() {
                match depend {
                    Step::Command(cmd) => self.exec_command(&cmd, &data, &job.log),
                    Step::Job {
                        job: jobname,
                        props,
                        env,
                    } => {
                        let mut inner_data = data.clone();
                        if let Some(p) = props {
                            inner_data.props.extend(p.clone());
                        }
                        if let Some(e) = env {
                            inner_data.env.extend(e.clone());
                        }
                        return self.run_job(self.get_job(jobname).unwrap(), Some(&mut inner_data));
                    }
                };
            }
        }

        if job.steps.is_none() {
            let mut completed = job.completed.lock().unwrap();
            *completed = true;
            return true;
        }

        match &job.iters {
            Iteration::File(path) => {
                let iters = deserialize_file::<Vec<Value>>(path).unwrap();
                for iter in iters {
                    data.iter = Some(serde_json::json!(iter));
                    if let Some(raw_msg) = &job.message {
                        let msg = self.ctx.render_template(raw_msg, &data).unwrap();
                        println!("{}", msg);
                    };
                    if let Some(templates) = &job.templates {
                        let res = self.exec_templates(&templates, &data);
                        if job.ignore_errors && !res {
                            return false;
                        }
                    }
                    self.run_steps(&job, &mut data);
                }
            }
            Iteration::Loop(is_loop) => {
                let mut iter = 0;
                data.iter = Some(serde_json::json!(iter));
                if *is_loop {
                    loop {
                        data.iter = Some(serde_json::json!(iter));
                        if let Some(raw_msg) = &job.message {
                            let msg = self.ctx.render_template(raw_msg, &data).unwrap();
                            println!("{}", msg);
                        };
                        if let Some(templates) = &job.templates {
                            self.exec_templates(&templates, &data);
                        }
                        self.run_steps(&job, &mut data);
                        iter += 1;
                    }
                } else {
                    self.run_steps(&job, &mut data);
                }
            }
            Iteration::Values(values) => {
                for iter in values {
                    data.iter = Some(serde_json::json!(iter));
                    if let Some(raw_msg) = &job.message {
                        let msg = self.ctx.render_template(raw_msg, &data).unwrap();
                        println!("{}", msg);
                    };
                    if let Some(templates) = &job.templates {
                        self.exec_templates(&templates, &data);
                    }
                    self.run_steps(&job, &mut data);
                }
            }
            Iteration::Range { from, to: end, by } => {
                let start = from.unwrap_or(0);
                let step = by.unwrap_or(1);
                let mut counter = start;
                while counter != *end {
                    data.iter = Some(serde_json::json!(counter));
                    if let Some(raw_msg) = &job.message {
                        let msg = self.ctx.render_template(raw_msg, &data).unwrap();
                        println!("{}", msg);
                    };
                    if let Some(templates) = &job.templates {
                        self.exec_templates(&templates, &data);
                    }
                    self.run_steps(&job, &mut data);
                    counter += step;
                }
            }
        }

        // TODO: Refactor iterations into a single loop
        // let iters: Vec<Value> = Vec::new();
        // for i in iters {
        // }

        let mut completed = job.completed.lock().unwrap();
        *completed = true;
        return true;
    }

    /// Run all jobs sequentially
    pub fn run_all_jobs(&mut self) -> Result<()> {
        for job in self.jobs.iter() {
            self.run_job(job, None);
        }
        Ok(())
    }
}
