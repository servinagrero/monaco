use clap::Parser;
use std::process::exit;

mod config;
mod job;
mod runner;

use crate::config::*;
use crate::runner::*;

/// Execute jobs from a config file
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Path to the config file
    #[arg(short, long)]
    config: String,

    /// Name of the job to execute
    #[arg(short, long)]
    job: Option<String>,

    /// Run in dry mode (Don't execute steps, just print them)
    #[arg(long, default_value_t = false)]
    dry: bool,
}

fn main() -> Result<(), ()> {
    let args = Args::parse();

    let config = match Config::from_file(&args.config) {
        Ok(cfg) => cfg,
        Err(e) => {
            println!("Could not read configuration => {}", e);
            exit(1);
        }
    };

    if !config.check() {
        println!("Errors in the configuration.");
        exit(1);
    }

    let config_path = std::fs::canonicalize(args.config)
        .map_err(|err| eprintln!("Could not get path of config => {}", err))
        .unwrap();
    let config_dir = config_path.as_path().parent().unwrap().to_str().unwrap();

    let mut runner = Runner::new(&config, &config_dir);
    runner.dry_mode = args.dry;

    if let Some(jobname) = args.job {
        match runner.get_job(&jobname) {
            Some(job) => {
                let sucess = runner.run_job(job);
                exit(if sucess { 0 } else { 1 });
            }
            None => {
                let names = runner.get_job_names();
                println!("Job '{jobname}' does not exist");
                println!("Possible jobs are => {:?}", names.join(", "));
                exit(1);
            }
        }
    };

    runner.run_all();
    Ok(())
}
