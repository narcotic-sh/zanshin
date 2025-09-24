#![allow(non_camel_case_types)]

use std::path::PathBuf;
use std::ffi::CStr;
use std::process::{Command, Child};
use std::thread;
use serde_json::Value;
use tauri::{AppHandle, Manager};
use std::sync::Mutex;
use zmq;
use libc;

/*
=========================================================
    Tauri AppState
=========================================================
*/

#[derive(Debug)]
pub enum ZanshinStatus {
    LAUNCHING,
    RUNNING,
    PROCESSOR_WARMED_UP,
    UNKNOWN
}

#[derive(Default)]
pub struct AppState {
    pub first_run: Option<bool>,
    pub python_process: Option<Child>,
    pub status: Option<ZanshinStatus>,
    pub app_support: Option<PathBuf>
}

/*
=========================================================
    get_zanshin_application_support_path
=========================================================
*/

pub fn get_real_home_directory() -> PathBuf {
    unsafe {
        let passwd = libc::getpwuid(libc::getuid());
        if !passwd.is_null() {
            let home_dir_c = (*passwd).pw_dir;
            if !home_dir_c.is_null() {
                let home_dir = CStr::from_ptr(home_dir_c).to_string_lossy().into_owned();
                return PathBuf::from(home_dir);
            }
        }
        // Fallback to the environment variable if for some reason the above fails
        PathBuf::from(std::env::var("HOME").unwrap_or_default())
    }
}

pub fn get_zanshin_application_support_path() -> PathBuf {
    let mut path = get_real_home_directory();
    path.push("Library");
    path.push("Application Support");
    path.push("Zanshin");
    path
}

pub fn pathbuf_to_string(path: &PathBuf) -> Result<String, String> {
    path.to_str()
        .ok_or_else(|| "Invalid path".to_string())
        .map(String::from)
}

/*
=========================================================
    run_uv_pip_install
=========================================================
*/

pub fn run_uv_pip_install(app_support: &std::path::Path) {
    let uv_path = app_support.join("zanshin/third_party/uv/uv");
    let python_path = app_support.join("zanshin/python_interpreter/cpython-3.11.13-macos-aarch64-none/bin/python");
    let uv_path_str = pathbuf_to_string(&uv_path).unwrap();
    let python_path_str = pathbuf_to_string(&python_path).unwrap();

    // Removed uv pip install -r requirements.txt call on every run becuase:
    //   The purpose of it was to install new packages that get entered into requirements.txt through Zanshin updates.
    //   However, a new package could either have binary components or change an existing package with binary components
    //       by making another version of it get installed. In either case, you might end up with fresh unsigned binaries,
    //       which the OS will not allow to run, thereby breaking the entire Zanshin installation.
    // Therefore, we only update yt-dlp (if user setting allows), since yt-dlp is pure Python, no binary components.

    let _ = Command::new(&uv_path_str)
        .args([
            "pip", "install",
            "--upgrade", "--pre",
            "--python", &python_path_str,
            "yt-dlp[default]",
            "--break-system-packages"
        ])
        .status();
}

/*
=========================================================
    launch_python
=========================================================
*/

pub fn launch_python(app_support: &std::path::Path, first_run: bool) -> Child {
    let interpreter_path = pathbuf_to_string(&app_support.join("zanshin/python_interpreter/cpython-3.11.13-macos-aarch64-none/bin/python")).unwrap();
    let script_path = pathbuf_to_string(&app_support.join("zanshin/src/app.py")).unwrap();

    let mut command = Command::new(&interpreter_path);
    command.arg(&script_path)
           .arg("--no-browser");

    if first_run {
        command.arg("--first-run");
    }

    return command
        .spawn()
        .expect("Failed to spawn python interpreter process")
}

/*
=========================================================
    First run management
=========================================================
*/

pub fn first_run_file_exists(app_support: PathBuf) -> bool {
    app_support
        .join("first_run")
        .exists()
}

pub fn create_first_run_file(app_support: PathBuf) {
    let path = app_support.join("first_run");
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).unwrap();
    }
    std::fs::write(&path, "").unwrap();
}

/*
=========================================================
    open_browser
=========================================================
*/

pub fn open_browser(url: &str) {
    Command::new("open")
        .arg(url)
        .spawn();
}

/*
=========================================================
    ZeroMQ
=========================================================
*/

pub fn start_zmq_listener(app: AppHandle, window: tauri::Window) {
    thread::spawn(move || {
        let context = zmq::Context::new();
        let socket = match context.socket(zmq::PULL) {
            Ok(socket) => socket,
            Err(_) => return,
        };

        if socket.bind("tcp://127.0.0.1:5555").is_err() {
            eprintln!("Failed to bind ZMQ socket");
            return;
        }

        println!("ZMQ listener started");
        loop {
            if let Ok(Ok(message)) = socket.recv_string(0) {
                println!("Received ZMQ message: {}", message);

                if let Ok(json_value) = serde_json::from_str::<Value>(&message) {
                    if let Some(status) = json_value.get("status").and_then(|s| s.as_str()) {
                        println!("Status: {}", status);

                        match status {
                            "started app" => {
                                app.state::<Mutex<AppState>>().lock().unwrap().status = Some(ZanshinStatus::RUNNING);

                                // Create first_run file
                                if app.state::<Mutex<AppState>>().lock().unwrap().first_run == Some(true) {
                                    create_first_run_file(app.state::<Mutex<AppState>>().lock().unwrap().app_support.clone().unwrap());
                                }
                            },
                            "processor warmed up" => {
                                app.state::<Mutex<AppState>>().lock().unwrap().status = Some(ZanshinStatus::PROCESSOR_WARMED_UP);
                            },
                            _ => {
                                app.state::<Mutex<AppState>>().lock().unwrap().status = Some(ZanshinStatus::UNKNOWN);
                            }
                        }

                        if status == "started app" {
                            let window_clone = window.clone();
                            thread::spawn(move || {
                                thread::sleep(std::time::Duration::from_secs(5));
                                window_clone.hide();
                                open_browser("http://localhost:1776");
                            });
                        }
                    }
                }
            }
        }
    });
}

/*
=========================================================
    Cleanup
=========================================================
*/

pub fn cleanup(app_handle: &AppHandle) {
    println!("Running cleanup...");
    let state = app_handle.state::<Mutex<AppState>>();

    if let Some(mut child) = state.lock().unwrap().python_process.take() {
        // First attempt: Send SIGTERM for graceful shutdown
        println!("Sending SIGTERM to Python process...");
        let pid = child.id() as i32;

        // Send SIGTERM signal
        unsafe {
            libc::kill(pid, libc::SIGTERM);
        }

        // Define 5 sec timeout duration
        let timeout = std::time::Duration::from_secs(5);
        let start = std::time::Instant::now();

        // Check if the process terminates within timeout period
        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    println!("Python process terminated gracefully with status: {}", status);
                    break;
                }
                Ok(None) => {
                    // Process still running
                    if start.elapsed() >= timeout {
                        // Timeout exceeded, use SIGKILL
                        println!("Timeout exceeded, forcing termination with SIGKILL");
                        match child.kill() {
                            Ok(_) => {
                                match child.wait() {
                                    Ok(status) => println!("Python process forcefully terminated with status: {}", status),
                                    Err(e) => eprintln!("Error waiting for Python process after SIGKILL: {}", e),
                                }
                            },
                            Err(e) => eprintln!("Failed to send SIGKILL to Python process: {}", e),
                        }
                        break;
                    }
                    // Small sleep to avoid CPU spinning
                    std::thread::sleep(std::time::Duration::from_millis(100));
                }
                Err(e) => {
                    eprintln!("Error checking Python process status: {}", e);
                    // Try SIGKILL as a fallback
                    match child.kill() {
                        Ok(_) => println!("Python process forcefully terminated"),
                        Err(e) => eprintln!("Failed to forcefully terminate Python process: {}", e),
                    }
                    break;
                }
            }
        }
    }

    println!("Cleanup complete");
}

/*
=========================================================
    check_internet_connection()
=========================================================
*/

pub fn check_internet_connection() -> bool {
    match Command::new("ping")
        .args(["-c", "1", "-W", "2", "1.1.1.1"])  // Linux/macOS args
        // Use .args(["-n", "1", "-w", "2000", "1.1.1.1"]) for Windows
        .output() {
            Ok(output) => output.status.success(),
            Err(_) => false,
        }
}

/*
=========================================================
    vacuum_media_db
=========================================================
*/

pub fn vacuum_media_db(app_support: &PathBuf) -> Result<(), String> {
    use rusqlite::Connection;

    // Correct path: app_support/zanshin/media.db
    let db_path = app_support.join("zanshin").join("media.db");

    // Check if database exists
    if !db_path.exists() {
        println!("media.db not found at {:?}, skipping vacuum", db_path);
        return Ok(());
    }

    println!("Vacuuming media.db...");

    match Connection::open(&db_path) {
        Ok(conn) => {
            match conn.execute("VACUUM", []) {
                Ok(_) => {
                    println!("Successfully vacuumed media.db");
                    Ok(())
                }
                Err(e) => {
                    let error_msg = format!("Failed to vacuum media.db: {}", e);
                    eprintln!("{}", error_msg);
                    Err(error_msg)
                }
            }
        }
        Err(e) => {
            let error_msg = format!("Failed to open media.db: {}", e);
            eprintln!("{}", error_msg);
            Err(error_msg)
        }
    }
}