use anyhow::Result;
use clap::Parser;
use std::process::exit;

use monaco::config::Config;
use monaco::runner::Runner;

/// Execute jobs from a configuration file
///
/// Configuration can be in either YAML, TOML or JSON format.
#[derive(Parser, Debug)]
#[command(author, version, about, long_about)]
struct Args {
    /// Path to the configuration file
    #[arg(short, long)]
    config: String,

    /// Name of the job to execute
    #[arg(short, long)]
    job: Option<String>,

    /// Run in dry mode (Don't execute steps, just print them)
    #[arg(long, default_value_t = false)]
    dry: bool,
}

fn main() -> Result<()> {
    let args = Args::parse();

    let config = Config::from_file(&args.config)?;
    let mut runner = Runner::from_config(&config)?;
    runner.dry_mode = args.dry;

    if let Some(jobname) = args.job {
        match runner.get_job(&jobname) {
            Some(job) => {
                let sucess = runner.run_job(job, None);
                exit(if sucess { 0 } else { 1 });
            }
            None => {
                let names: Vec<&str> = runner
                    .jobs
                    .iter()
                    .map(|j| j.name.as_str())
                    .collect::<Vec<_>>();

                anyhow::bail!(
                    "Job '{jobname}' does not exist. Possible jobs are => {:?}",
                    names.join(", ")
                );
            }
        }
    };

    return runner.run_all_jobs();
}
