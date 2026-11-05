// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::io::Write;
use std::net::TcpStream;
use std::sync::Mutex;

use tauri::{Manager, State, WindowEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

struct Backend {
    base: String,
    port: u16,
    child: Mutex<Option<CommandChild>>,
}

#[tauri::command]
fn api_base(state: State<'_, Backend>) -> String {
    state.base.clone()
}

fn free_port() -> u16 {
    std::net::TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|address| address.port())
        .unwrap_or(8765)
}

fn stop_backend(app: &tauri::AppHandle) {
    if let Some(backend) = app.try_state::<Backend>() {
        if let Ok(mut stream) = TcpStream::connect(("127.0.0.1", backend.port)) {
            let _ = stream.write_all(
                b"POST /api/shutdown HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            );
        }
        if let Some(child) = backend.child.lock().unwrap().take() {
            let _ = child.kill();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let port = free_port();
            let sidecar = app
                .shell()
                .sidecar("viral-server")?
                .args([
                    "--host",
                    "127.0.0.1",
                    "--port",
                    &port.to_string(),
                    "--parent-pid",
                    &std::process::id().to_string(),
                ]);
            let (mut rx, child) = sidecar.spawn()?;

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            println!("[viral-server] {}", String::from_utf8_lossy(&line).trim())
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("[viral-server] {}", String::from_utf8_lossy(&line).trim())
                        }
                        CommandEvent::Error(error) => eprintln!("[viral-server] {error}"),
                        _ => {}
                    }
                }
            });

            app.manage(Backend {
                base: format!("http://127.0.0.1:{port}"),
                port,
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                stop_backend(window.app_handle());
                window.app_handle().exit(0);
            }
        })
        .invoke_handler(tauri::generate_handler![api_base])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app, event| {
        if let tauri::RunEvent::Exit = event {
            stop_backend(app);
        }
    });
}
