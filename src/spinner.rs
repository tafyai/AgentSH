//! Progress spinner for long-running operations
//!
//! Provides visual feedback during AI calls and other async operations.

#![allow(dead_code)]

use std::io::{self, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;

/// Spinner animation frames
const SPINNER_FRAMES: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

/// Dots animation frames
const DOTS_FRAMES: &[&str] = &["   ", ".  ", ".. ", "..."];

/// Simple spinner frames (ASCII fallback)
const SIMPLE_FRAMES: &[&str] = &["|", "/", "-", "\\"];

/// Spinner style
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub enum SpinnerStyle {
    /// Unicode braille spinner
    #[default]
    Braille,
    /// Simple dots
    Dots,
    /// ASCII spinner (fallback)
    Simple,
}

impl From<&str> for SpinnerStyle {
    fn from(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "dots" => Self::Dots,
            "simple" | "ascii" => Self::Simple,
            _ => Self::Braille,
        }
    }
}

/// Progress spinner for visual feedback
pub struct Spinner {
    message: String,
    style: SpinnerStyle,
    running: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl Spinner {
    /// Create a new spinner with a message
    pub fn new(message: &str) -> Self {
        Self {
            message: message.to_string(),
            style: SpinnerStyle::default(),
            running: Arc::new(AtomicBool::new(false)),
            handle: None,
        }
    }

    /// Set the spinner style
    pub fn with_style(mut self, style: SpinnerStyle) -> Self {
        self.style = style;
        self
    }

    /// Start the spinner animation
    pub fn start(&mut self) {
        if self.running.load(Ordering::Relaxed) {
            return; // Already running
        }

        self.running.store(true, Ordering::Relaxed);

        let running = self.running.clone();
        let message = self.message.clone();
        let frames = match self.style {
            SpinnerStyle::Braille => SPINNER_FRAMES,
            SpinnerStyle::Dots => DOTS_FRAMES,
            SpinnerStyle::Simple => SIMPLE_FRAMES,
        };

        let handle = thread::spawn(move || {
            let mut frame_idx = 0;
            let mut stdout = io::stderr();

            while running.load(Ordering::Relaxed) {
                let frame = frames[frame_idx % frames.len()];

                // Write spinner frame
                let _ = write!(stdout, "\r\x1b[K{} {}", frame, message);
                let _ = stdout.flush();

                frame_idx += 1;
                thread::sleep(Duration::from_millis(80));
            }

            // Clear the line when done
            let _ = write!(stdout, "\r\x1b[K");
            let _ = stdout.flush();
        });

        self.handle = Some(handle);
    }

    /// Stop the spinner
    pub fn stop(&mut self) {
        self.running.store(false, Ordering::Relaxed);

        if let Some(handle) = self.handle.take() {
            let _ = handle.join();
        }
    }

    /// Stop with a success message
    pub fn stop_with_success(&mut self, message: &str) {
        self.stop();
        eprintln!("\x1b[32m✓\x1b[0m {}", message);
    }

    /// Stop with an error message
    pub fn stop_with_error(&mut self, message: &str) {
        self.stop();
        eprintln!("\x1b[31m✗\x1b[0m {}", message);
    }

    /// Stop with a warning message
    pub fn stop_with_warning(&mut self, message: &str) {
        self.stop();
        eprintln!("\x1b[33m!\x1b[0m {}", message);
    }

    /// Update the spinner message
    pub fn set_message(&mut self, message: &str) {
        self.message = message.to_string();
    }
}

impl Drop for Spinner {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Run an async operation with a spinner
pub async fn with_spinner<F, T>(message: &str, future: F) -> T
where
    F: std::future::Future<Output = T>,
{
    let mut spinner = Spinner::new(message);
    spinner.start();

    let result = future.await;

    spinner.stop();
    result
}

/// Simple progress indicator (non-animated)
pub struct ProgressIndicator {
    total: usize,
    current: usize,
    message: String,
}

impl ProgressIndicator {
    /// Create a new progress indicator
    pub fn new(message: &str, total: usize) -> Self {
        Self {
            total,
            current: 0,
            message: message.to_string(),
        }
    }

    /// Update progress
    pub fn update(&mut self, current: usize) {
        self.current = current;
        self.render();
    }

    /// Increment progress by one
    pub fn inc(&mut self) {
        self.current += 1;
        self.render();
    }

    /// Render the progress
    fn render(&self) {
        let percent = if self.total > 0 {
            (self.current * 100) / self.total
        } else {
            0
        };

        eprint!(
            "\r\x1b[K{} [{}/{}] {}%",
            self.message, self.current, self.total, percent
        );
        let _ = io::stderr().flush();
    }

    /// Finish with a message
    pub fn finish(&self, message: &str) {
        eprintln!("\r\x1b[K{}", message);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spinner_style_from_str() {
        assert_eq!(SpinnerStyle::from("dots"), SpinnerStyle::Dots);
        assert_eq!(SpinnerStyle::from("simple"), SpinnerStyle::Simple);
        assert_eq!(SpinnerStyle::from("ascii"), SpinnerStyle::Simple);
        assert_eq!(SpinnerStyle::from("braille"), SpinnerStyle::Braille);
        assert_eq!(SpinnerStyle::from("unknown"), SpinnerStyle::Braille);
    }

    #[test]
    fn test_spinner_default_style() {
        assert_eq!(SpinnerStyle::default(), SpinnerStyle::Braille);
    }

    #[test]
    fn test_spinner_create() {
        let spinner = Spinner::new("Loading...");
        assert_eq!(spinner.message, "Loading...");
        assert!(!spinner.running.load(Ordering::Relaxed));
    }

    #[test]
    fn test_spinner_with_style() {
        let spinner = Spinner::new("Test").with_style(SpinnerStyle::Dots);
        assert_eq!(spinner.style, SpinnerStyle::Dots);
    }

    #[test]
    fn test_spinner_start_stop() {
        let mut spinner = Spinner::new("Test");
        spinner.start();
        assert!(spinner.running.load(Ordering::Relaxed));

        thread::sleep(Duration::from_millis(100));

        spinner.stop();
        assert!(!spinner.running.load(Ordering::Relaxed));
    }

    #[test]
    fn test_spinner_double_start() {
        let mut spinner = Spinner::new("Test");
        spinner.start();
        spinner.start(); // Should not panic or create second thread
        spinner.stop();
    }

    #[test]
    fn test_progress_indicator() {
        let mut progress = ProgressIndicator::new("Processing", 10);
        assert_eq!(progress.current, 0);
        assert_eq!(progress.total, 10);

        progress.inc();
        assert_eq!(progress.current, 1);

        progress.update(5);
        assert_eq!(progress.current, 5);
    }
}
