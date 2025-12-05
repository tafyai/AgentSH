# frozen_string_literal: true

# Homebrew formula for AgentSH
# Install: brew install agentsh/tap/agentsh
# Or:      brew tap agentsh/tap && brew install agentsh

class Agentsh < Formula
  include Language::Python::Virtualenv

  desc "AI-enhanced terminal shell with natural language command generation"
  homepage "https://github.com/agentsh/agentsh"
  url "https://files.pythonhosted.org/packages/source/a/agentsh/agentsh-0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"
  head "https://github.com/agentsh/agentsh.git", branch: "main"

  depends_on "python@3.11"

  # Core dependencies
  resource "anthropic" do
    url "https://files.pythonhosted.org/packages/source/a/anthropic/anthropic-0.40.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/source/h/httpx/httpx-0.27.2.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "prompt-toolkit" do
    url "https://files.pythonhosted.org/packages/source/p/prompt_toolkit/prompt_toolkit-3.0.48.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.9.4.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic/pydantic-2.9.2.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/p/PyYAML/pyyaml-6.0.2.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.7.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "ptyprocess" do
    url "https://files.pythonhosted.org/packages/source/p/ptyprocess/ptyprocess-0.7.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "wcwidth" do
    url "https://files.pythonhosted.org/packages/source/w/wcwidth/wcwidth-0.2.13.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/source/p/pygments/pygments-2.18.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  def install
    virtualenv_install_with_resources

    # Generate shell completions
    generate_completions_from_executable(bin/"agentsh", "--completions", shells: [:bash, :zsh, :fish])
  end

  def post_install
    # Add to /etc/shells if not present
    shells_file = "/etc/shells"
    agentsh_path = "#{HOMEBREW_PREFIX}/bin/agentsh"

    if File.exist?(shells_file)
      shells_content = File.read(shells_file)
      unless shells_content.include?(agentsh_path)
        ohai "To use AgentSH as a login shell, add it to /etc/shells:"
        ohai "  echo '#{agentsh_path}' | sudo tee -a /etc/shells"
      end
    end
  end

  def caveats
    <<~EOS
      AgentSH has been installed!

      To start using AgentSH:
        agentsh

      To configure your API keys:
        agentsh config init

      To set AgentSH as your default shell:
        1. Add to /etc/shells:
           echo '#{HOMEBREW_PREFIX}/bin/agentsh' | sudo tee -a /etc/shells
        2. Change your shell:
           chsh -s #{HOMEBREW_PREFIX}/bin/agentsh

      For more information:
        https://github.com/agentsh/agentsh
    EOS
  end

  test do
    assert_match "agentsh", shell_output("#{bin}/agentsh --version")

    # Test help output
    assert_match "AI-enhanced", shell_output("#{bin}/agentsh --help")

    # Test that it starts (with immediate exit)
    system bin/"agentsh", "--help"
  end
end
