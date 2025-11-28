# Development Guide

This guide covers setting up a development environment for agentsh and contributing to the project.

## Prerequisites

### Required

- **Rust** 1.75+ (install via [rustup](https://rustup.rs/))
- **Git**
- **C compiler** (for native dependencies)

### Optional

- **Docker** (for integration testing)
- **Make** (for convenience commands)

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/yourusername/agentsh.git
cd agentsh
```

### Build

```bash
# Debug build
cargo build

# Release build
cargo build --release
```

### Run

```bash
# Run debug build
cargo run

# Run with arguments
cargo run -- --help
cargo run -- --debug /bin/bash
```

### Test

```bash
# Run all tests
cargo test

# Run specific test
cargo test test_pty_spawn

# Run with output
cargo test -- --nocapture

# Run integration tests
cargo test --test integration
```

## Project Structure

```
agentsh/
├── Cargo.toml              # Package manifest
├── Cargo.lock              # Dependency lock file
├── src/
│   ├── main.rs             # Entry point, CLI parsing
│   ├── lib.rs              # Library root
│   ├── pty.rs              # PTY management
│   ├── input_router.rs     # Input routing logic
│   ├── ai_orchestrator.rs  # LLM communication
│   ├── execution_engine.rs # Command execution
│   ├── context.rs          # System context collection
│   ├── config.rs           # Configuration loading
│   ├── safety.rs           # Destructive command detection
│   └── logging.rs          # Audit logging
├── tests/
│   ├── integration/        # Integration tests
│   │   ├── pty_tests.rs
│   │   ├── ai_tests.rs
│   │   └── e2e_tests.rs
│   └── fixtures/           # Test fixtures
├── docs/                   # Documentation
├── contrib/                # Plugins and extensions
│   └── plugins/
├── scripts/                # Development scripts
│   ├── install.sh
│   └── test-in-docker.sh
└── examples/               # Example configurations
    ├── config.toml
    └── aishellrc
```

## Development Workflow

### Branch Naming

```
feature/description    # New features
fix/description        # Bug fixes
docs/description       # Documentation
refactor/description   # Code refactoring
test/description       # Test additions
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add ai explain command
fix: handle pty resize on macOS
docs: add configuration reference
refactor: extract safety module
test: add integration tests for execution engine
```

### Pull Request Process

1. Create a feature branch
2. Make changes with tests
3. Run `cargo fmt` and `cargo clippy`
4. Submit PR with description
5. Address review feedback
6. Squash and merge

## Code Style

### Formatting

```bash
# Format code
cargo fmt

# Check formatting
cargo fmt -- --check
```

### Linting

```bash
# Run clippy
cargo clippy

# Run clippy with all warnings as errors
cargo clippy -- -D warnings
```

### Code Guidelines

- Use `Result` for fallible operations
- Prefer `?` operator over explicit matching
- Document public APIs with rustdoc
- Keep functions small and focused
- Write tests for new functionality

## Dependencies

### Key Crates

| Crate | Purpose |
|-------|---------|
| `nix` | POSIX/PTY operations |
| `tokio` | Async runtime |
| `rustyline` / `reedline` | Line editing |
| `serde` | Serialization |
| `toml` | Configuration parsing |
| `reqwest` | HTTP client |
| `tracing` | Logging/diagnostics |

### Adding Dependencies

Add to `Cargo.toml`:

```toml
[dependencies]
new-crate = "1.0"
```

For optional features:

```toml
[features]
experimental = ["new-crate"]

[dependencies]
new-crate = { version = "1.0", optional = true }
```

## Testing

### Unit Tests

Place unit tests in the same file as the code:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_something() {
        assert_eq!(something(), expected);
    }
}
```

### Integration Tests

Place in `tests/` directory:

```rust
// tests/integration/pty_tests.rs
use agentsh::pty::PtyShell;

#[test]
fn test_pty_spawn() {
    let shell = PtyShell::spawn("/bin/sh", &[]).unwrap();
    assert!(shell.is_running());
}
```

### Test Fixtures

Use `tests/fixtures/` for test data:

```rust
let config = include_str!("../fixtures/test_config.toml");
```

### Mocking

For AI backend testing, use mock responses:

```rust
#[cfg(test)]
mod tests {
    use mockito::Server;

    #[tokio::test]
    async fn test_ai_call() {
        let mut server = Server::new();

        let mock = server.mock("POST", "/v1/chat/completions")
            .with_status(200)
            .with_body(include_str!("fixtures/ai_response.json"))
            .create();

        // Test code using server.url()

        mock.assert();
    }
}
```

## Debugging

### Enable Debug Output

```bash
# Via environment variable
AISHELL_DEBUG=true cargo run

# Via CLI flag
cargo run -- --debug
```

### Tracing

```rust
use tracing::{debug, info, error};

fn process_input(input: &str) {
    debug!("Processing input: {:?}", input);

    if let Err(e) = do_something() {
        error!("Failed: {:?}", e);
    }
}
```

View with subscriber:

```bash
RUST_LOG=debug cargo run
```

### PTY Debugging

For PTY issues, log raw bytes:

```rust
debug!("PTY read: {:02x?}", bytes);
debug!("PTY write: {:02x?}", data);
```

## Performance Profiling

### Build with Profiling

```bash
cargo build --release --profile profiling
```

### Profile with flamegraph

```bash
cargo install flamegraph
cargo flamegraph --root -- /bin/bash
```

### Benchmarks

Add benchmarks in `benches/`:

```rust
// benches/safety.rs
use criterion::{criterion_group, criterion_main, Criterion};
use agentsh::safety::analyze_command;

fn bench_analyze(c: &mut Criterion) {
    c.bench_function("analyze_command", |b| {
        b.iter(|| analyze_command("rm -rf /tmp/test"))
    });
}

criterion_group!(benches, bench_analyze);
criterion_main!(benches);
```

Run:

```bash
cargo bench
```

## Release Process

### Version Bump

1. Update `Cargo.toml` version
2. Update `CHANGELOG.md`
3. Create git tag

```bash
# Update version
vim Cargo.toml

# Update changelog
vim CHANGELOG.md

# Commit and tag
git add .
git commit -m "chore: release v0.2.0"
git tag v0.2.0
git push origin main --tags
```

### Build Release Binaries

```bash
# Linux x86_64
cargo build --release --target x86_64-unknown-linux-gnu

# macOS x86_64
cargo build --release --target x86_64-apple-darwin

# macOS ARM64
cargo build --release --target aarch64-apple-darwin
```

### Cross-Compilation

Using `cross`:

```bash
cargo install cross

# Build for Linux from macOS
cross build --release --target x86_64-unknown-linux-gnu
```

## Common Tasks

### Regenerate Test Fixtures

```bash
./scripts/generate-fixtures.sh
```

### Run in Docker

```bash
./scripts/test-in-docker.sh
```

### Update Dependencies

```bash
cargo update
cargo test
```

### Check for Security Vulnerabilities

```bash
cargo install cargo-audit
cargo audit
```

## Troubleshooting

### PTY Tests Fail on CI

PTY tests may fail in containerized CI environments. Use Docker with TTY:

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: cargo test
        # For PTY tests
        env:
          TERM: xterm-256color
```

### Build Fails on macOS

Ensure Xcode Command Line Tools are installed:

```bash
xcode-select --install
```

### Linker Errors

Install required libraries:

```bash
# Ubuntu/Debian
sudo apt install build-essential libssl-dev pkg-config

# macOS
brew install openssl
```

## IDE Setup

### VS Code

Recommended extensions:
- rust-analyzer
- Even Better TOML
- CodeLLDB (debugging)

`settings.json`:
```json
{
    "rust-analyzer.check.command": "clippy",
    "rust-analyzer.cargo.features": "all"
}
```

### JetBrains (RustRover/CLion)

Install Rust plugin and configure:
- Use rustfmt on save
- Enable clippy lints

## Resources

- [Rust Book](https://doc.rust-lang.org/book/)
- [Tokio Tutorial](https://tokio.rs/tokio/tutorial)
- [PTY Programming](https://man7.org/linux/man-pages/man7/pty.7.html)
- [rustyline docs](https://docs.rs/rustyline)
