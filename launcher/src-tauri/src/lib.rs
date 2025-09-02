#![allow(unused_must_use)]

use tauri::{AppHandle, Manager, Emitter};
use std::thread;
use std::sync::Mutex;
use std::process::Command;

mod misc;

/*
=========================================================
    Remove camel case from args
=========================================================
*/

#[macro_export]
macro_rules! tauri_command {
    ($(#[$attr:meta])* $vis:vis fn $name:ident($($arg:ident : $type:ty),*) $(-> $ret:ty)? $body:block) => {
        #[tauri::command(rename_all = "snake_case")]
        $(#[$attr])*
        $vis fn $name($($arg: $type),*) $(-> $ret)? $body
    };
}

/*
=========================================================
    Tauri Commands
=========================================================
*/

tauri_command! {
    fn initialize(app: AppHandle, window: tauri::Window) {

        // Show window, set focus
        window.show();
        window.set_focus();

        let state = app.state::<Mutex<misc::AppState>>();

        // ~/Library/Application Support/Zanshin
        let app_support = misc::get_zanshin_application_support_path();
        state.lock().unwrap().app_support = Some(app_support.clone());

        // Check if first run
        let first_run = !misc::first_run_file_exists(app_support.clone());
        state.lock().unwrap().first_run = Some(first_run);

        // Clone Tauri app instance & window for thread
        let app_clone = app.clone();
        let window_clone = window.clone();

        // Seperate thread to launch Python process
        thread::spawn(move || {

            // Launch Python interpreter process
            app_clone
                .state::<Mutex<misc::AppState>>()
                .lock()
                .unwrap()
                .status = Some(misc::ZanshinStatus::LAUNCHING);

            app_clone.emit("zmq_notification", serde_json::json!({
                "status": "Launching",
                "is_first_run": first_run
            })).unwrap();

            // If we have internet access, upgrade yt-dlp before launch
            if misc::check_internet_connection() {
                misc::run_uv_pip_install(&app_support);
            }

            let child = misc::launch_python(&app_support, first_run);

            // Put Python interpreter process handle into AppState
            let state = app_clone.state::<Mutex<misc::AppState>>();
            state.lock().unwrap().python_process = Some(child);
            println!("Python process started successfully");

            // Start listener for Python interpreter process messages
            misc::start_zmq_listener(app_clone, window_clone);
            println!("ZeroMQ listener launched");

        });

    }
}

tauri_command! {
    fn open_tiger_video() {
        misc::open_browser("https://www.youtube.com/embed/Znpnf9D2VIk?autoplay=1");
    }
}

/*
=========================================================
    Tauri run()
=========================================================
*/

pub fn run() {

    // Configure app
    let builder = tauri::Builder::default()

        // Allows opening files and URLs in a specified, or the default, application
        .plugin(tauri_plugin_opener::init())

        // tauri_command! functions
        .invoke_handler(tauri::generate_handler![
            initialize,
            open_tiger_video
        ])

        // Runs once at beginning, before main event loop starts
        .setup(|app| {
            app.manage(Mutex::new(misc::AppState {
                first_run: None,
                python_process: None,
                status: None,
                app_support: None
            }));
            Ok(())
        });

    // Apply config (build)
    let app = builder
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    // Run
    app.run(|app_handle, event| match event {
        tauri::RunEvent::Reopen { .. } => {
            match app_handle.state::<Mutex<misc::AppState>>().lock().unwrap().status {
                Some(misc::ZanshinStatus::RUNNING) | Some(misc::ZanshinStatus::PROCESSOR_WARMED_UP) => {
                    misc::open_browser("http://localhost:1776");
                },
                _ => {}  // do nothing
            }
        }
        tauri::RunEvent::Exit => {
            println!("App is exiting");

            // Get app_support path before cleanup
            let app_support = misc::get_zanshin_application_support_path();

            // Run cleanup (terminates Python process)
            misc::cleanup(app_handle);

            // Vacuum the media.db after Python process is terminated
            if let Err(e) = misc::vacuum_media_db(&app_support) {
                eprintln!("Warning: {}", e);
                // Continue with exit even if vacuum fails
            }

            /* Run update.py if present */
            let update_dir = app_support.join("update");

            // Check if the update directory exists
            if update_dir.exists() && update_dir.is_dir() {
                let update_script = update_dir.join("update.py");

                // Check if update.py exists
                if update_script.exists() && update_script.is_file() {
                    // Path to the specific Python interpreter
                    let python_interpreter = app_support
                        .join("zanshin")
                        .join("python_interpreter")
                        .join("cpython-3.11.13-macos-aarch64-none")
                        .join("bin")
                        .join("python");

                    // Run the update script with the specified interpreter and wait for it to complete
                    let output = Command::new(&python_interpreter)
                        .arg(&update_script)
                        .output()
                        .unwrap();

                    println!("Update script execution completed");
                    println!("Exit status: {}", output.status);
                    println!("Output: {}", String::from_utf8_lossy(&output.stdout));

                    if !output.status.success() {
                        eprintln!("Error: {}", String::from_utf8_lossy(&output.stderr));
                    }
                } else {
                    println!("update.py not found in the update directory");
                }
            } else {
                println!("Update directory does not exist");
            }

        }
        _ => {}
    });
}