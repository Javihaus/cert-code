"""
CLI for cert-code.

Commands:
    cert-code submit     Submit code trace to CERT
    cert-code init       Initialize configuration
    cert-code hook       Install git hooks
    cert-code status     Check configuration and connectivity
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cert_code.collector import CodeCollector, CollectorOptions
from cert_code.config import CertCodeConfig
from cert_code.models import Language

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="cert-code")
def main() -> None:
    """CERT Code - Evaluate AI-generated code artifacts."""
    pass


@main.command()
@click.option(
    "--task",
    "-t",
    required=True,
    help="Task description (what was the AI asked to do)",
)
@click.option(
    "--diff",
    "-d",
    type=str,
    help="Diff string (if not using git)",
)
@click.option(
    "--ref",
    default="HEAD",
    help="Git reference (commit, branch, tag)",
)
@click.option(
    "--base-ref",
    help="Base reference for comparison",
)
@click.option(
    "--run-tests / --no-tests",
    default=None,
    help="Run tests after collecting artifact",
)
@click.option(
    "--run-lint / --no-lint",
    default=None,
    help="Run linter",
)
@click.option(
    "--run-typecheck / --no-typecheck",
    default=None,
    help="Run type checker",
)
@click.option(
    "--context",
    "-c",
    multiple=True,
    help="Context files to include (can be specified multiple times)",
)
@click.option(
    "--language",
    "-l",
    type=click.Choice([lang.value for lang in Language]),
    help="Override language detection",
)
@click.option(
    "--tool",
    help="Code generation tool name (e.g., claude-code, cursor)",
)
@click.option(
    "--project",
    "-p",
    help="CERT project ID",
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to config file",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be submitted without actually submitting",
)
def submit(
    task: str,
    diff: str | None,
    ref: str,
    base_ref: str | None,
    run_tests: bool | None,
    run_lint: bool | None,
    run_typecheck: bool | None,
    context: tuple[str, ...],
    language: str | None,
    tool: str | None,
    project: str | None,
    config: str | None,
    dry_run: bool,
) -> None:
    """Submit a code trace to CERT."""
    # Load config
    config_path = Path(config) if config else None
    cfg = CertCodeConfig.load(config_path)

    # Override with CLI args
    if project:
        cfg.project_id = project

    # Build options
    options = CollectorOptions(
        run_tests=run_tests if run_tests is not None else cfg.auto_run_tests,
        run_lint=run_lint if run_lint is not None else cfg.auto_run_lint,
        run_typecheck=run_typecheck if run_typecheck is not None else cfg.auto_run_typecheck,
        context_files=list(context) if context else None,
        language=Language(language) if language else None,
    )

    try:
        # Handle dry-run before creating collector (which requires API key)
        if dry_run:
            if diff:
                _show_dry_run(task, diff, options, tool)
            else:
                from cert_code.analyzers.diff import get_diff_from_git

                git_diff = get_diff_from_git(ref, base_ref)

                if not git_diff.strip():
                    console.print("[yellow]No changes found in commit[/yellow]")
                    sys.exit(1)

                _show_dry_run(task, git_diff, options, tool)
            return

        with CodeCollector(cfg) as collector:
            if diff:
                result = collector.from_diff(
                    task=task,
                    diff=diff,
                    options=options,
                    tool=tool,
                )
            else:
                # Get diff from git
                from cert_code.analyzers.diff import get_diff_from_git

                git_diff = get_diff_from_git(ref, base_ref)

                if not git_diff.strip():
                    console.print("[yellow]No changes found in commit[/yellow]")
                    sys.exit(1)

                result = collector.from_commit(
                    task=task,
                    ref=ref,
                    base_ref=base_ref,
                    options=options,
                    tool=tool,
                )

        # Display result
        if result.success:
            console.print(
                Panel(
                    f"[green]✓[/green] Trace submitted successfully\n\n"
                    f"Trace ID: [bold]{result.trace_id}[/bold]",
                    title="CERT Code",
                    border_style="green",
                )
            )

            # Show evaluation if available
            if result.evaluation:
                _show_evaluation(result.evaluation)
        else:
            console.print(
                Panel(
                    f"[red]✗[/red] Submission failed\n\n{result.error}",
                    title="CERT Code",
                    border_style="red",
                )
            )
            sys.exit(1)

    except ValueError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("\nRun [bold]cert-code init[/bold] to create a configuration file.")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing configuration",
)
def init(force: bool) -> None:
    """Initialize cert-code configuration."""
    config_path = Path(".cert-code.toml")

    if config_path.exists() and not force:
        console.print(
            f"[yellow]Configuration file already exists:[/yellow] {config_path}\n"
            "Use --force to overwrite."
        )
        sys.exit(1)

    # Create default config
    config = CertCodeConfig()
    config_content = config.to_toml()

    config_path.write_text(config_content)

    console.print(
        Panel(
            f"[green]✓[/green] Created configuration file: [bold]{config_path}[/bold]\n\n"
            "Next steps:\n"
            "1. Set your API key: [dim]export CERT_CODE_API_KEY=your-key[/dim]\n"
            "2. Set your project ID in the config file\n"
            "3. Run [bold]cert-code submit[/bold] to evaluate code",
            title="CERT Code Initialized",
            border_style="green",
        )
    )


@main.command()
@click.option(
    "--type",
    "-t",
    "hook_type",
    type=click.Choice(["post-commit", "pre-push"]),
    default="post-commit",
    help="Git hook type",
)
@click.option(
    "--uninstall",
    is_flag=True,
    help="Remove the git hook",
)
def hook(hook_type: str, uninstall: bool) -> None:
    """Install or remove git hooks for automatic submission."""
    from cert_code.hooks.install import install_hook, uninstall_hook

    if uninstall:
        if uninstall_hook(hook_type):
            console.print(f"[green]✓[/green] Removed {hook_type} hook")
        else:
            console.print(f"[yellow]Hook not found:[/yellow] {hook_type}")
    else:
        if install_hook(hook_type):
            console.print(f"[green]✓[/green] Installed {hook_type} hook")
            console.print(
                f"\nThe hook will run [bold]cert-code submit[/bold] after each "
                f"{hook_type.replace('-', ' ')}.\n"
                "Set [dim]CERT_CODE_TASK[/dim] environment variable to provide task description,\n"
                "or the hook will use the commit message."
            )
        else:
            console.print("[red]Failed to install hook[/red]")
            sys.exit(1)


@main.command()
def status() -> None:
    """Check configuration and connectivity."""
    config = CertCodeConfig.load()

    table = Table(title="CERT Code Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Status", style="green")

    # API URL
    table.add_row(
        "API URL",
        config.api_url,
        "✓" if config.api_url else "✗",
    )

    # API Key
    api_key_display = f"{config.api_key[:8]}..." if config.api_key else "Not set"
    table.add_row(
        "API Key",
        api_key_display,
        "✓" if config.api_key else "[red]✗[/red]",
    )

    # Project
    table.add_row(
        "Project ID",
        config.project_id or "Not set",
        "✓" if config.project_id else "[yellow]○[/yellow]",
    )

    # Config file
    config_file = CertCodeConfig._find_config_file()
    table.add_row(
        "Config File",
        str(config_file) if config_file else "None (using defaults)",
        "✓" if config_file else "[yellow]○[/yellow]",
    )

    console.print(table)

    # Test connectivity if API key is set
    if config.api_key:
        console.print("\nTesting connectivity...")
        try:
            import httpx

            response = httpx.get(
                f"{config.api_url.rstrip('/').replace('/v1', '')}/health",
                timeout=5.0,
            )
            if response.status_code == 200:
                console.print("[green]✓[/green] API is reachable")
            else:
                console.print(f"[yellow]○[/yellow] API returned status {response.status_code}")
        except Exception as e:
            console.print(f"[red]✗[/red] Cannot reach API: {e}")


def _show_dry_run(task: str, diff: str, options: CollectorOptions, tool: str | None) -> None:
    """Display what would be submitted in dry-run mode."""
    from cert_code.analyzers.diff import parse_diff

    artifact = parse_diff(diff, options.language)

    console.print(
        Panel(
            "[yellow]DRY RUN[/yellow] - Nothing will be submitted\n\n"
            f"[bold]Task:[/bold] {task}\n"
            f"[bold]Tool:[/bold] {tool or 'Not specified'}\n"
            f"[bold]Language:[/bold] {artifact.language.value}\n"
            f"[bold]Files changed:[/bold] {len(artifact.files_changed)}\n"
            f"[bold]Additions:[/bold] {artifact.diff_stats.additions}\n"
            f"[bold]Deletions:[/bold] {artifact.diff_stats.deletions}\n"
            f"[bold]Run tests:[/bold] {options.run_tests}\n"
            f"[bold]Run lint:[/bold] {options.run_lint}\n"
            f"[bold]Run typecheck:[/bold] {options.run_typecheck}",
            title="CERT Code - Dry Run",
            border_style="yellow",
        )
    )

    # Show files
    if artifact.files_changed:
        console.print("\n[bold]Files:[/bold]")
        for f in artifact.files_changed[:10]:
            console.print(f"  • {f}")
        if len(artifact.files_changed) > 10:
            console.print(f"  ... and {len(artifact.files_changed) - 10} more")


def _show_evaluation(evaluation: dict[str, Any]) -> None:
    """Display evaluation results."""
    table = Table(title="Evaluation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    # Standard metrics
    if "score" in evaluation:
        score = evaluation["score"]
        color = "green" if score >= 0.7 else "yellow" if score >= 0.5 else "red"
        table.add_row("Overall Score", f"[{color}]{score:.2%}[/{color}]")

    if "status" in evaluation:
        status = evaluation["status"]
        color = {"pass": "green", "review": "yellow", "fail": "red"}.get(status, "white")
        table.add_row("Status", f"[{color}]{status.upper()}[/{color}]")

    # Code-specific metrics
    metrics = evaluation.get("metrics", {})
    metric_names = {
        "code_execution_score": "Tests",
        "code_type_safety_score": "Type Safety",
        "code_lint_score": "Lint",
        "code_context_alignment_score": "Context Alignment (SGI)",
    }

    for key, display_name in metric_names.items():
        if key in metrics:
            value = metrics[key]
            color = "green" if value >= 0.7 else "yellow" if value >= 0.5 else "red"
            table.add_row(display_name, f"[{color}]{value:.2%}[/{color}]")

    console.print()
    console.print(table)


if __name__ == "__main__":
    main()
