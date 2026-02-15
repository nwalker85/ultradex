#!/usr/bin/env python3
"""
Ultradex CLI - Command-line interface for Ultradex API

Usage:
    ultradex analyze [--limit=N] [--wait=SECONDS]
    ultradex sync [--wait=SECONDS]
    ultradex status <operation_id>
    ultradex events <operation_id>
    ultradex --help
"""

import asyncio
import click
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sdk.ultradex_sdk import UltradexClient


def get_config():
    """Get configuration from environment or defaults"""
    return {
        "api_url": os.getenv("ULTRADEX_API_URL", "http://localhost:8000"),
        "api_key": os.getenv("ULTRADEX_API_KEY"),
    }


def format_timestamp(ts: Optional[str]) -> str:
    """Format timestamp for display"""
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts


def print_operation(op: dict, verbose: bool = False):
    """Pretty-print operation status"""
    click.echo(f"\n📋 Operation: {op['id']}")
    click.echo(f"   Status: {op['status']}")
    click.echo(f"   Created: {format_timestamp(op.get('created_at'))}")

    if op.get("started_at"):
        click.echo(f"   Started: {format_timestamp(op.get('started_at'))}")

    if op.get("completed_at"):
        click.echo(f"   Completed: {format_timestamp(op.get('completed_at'))}")

    if op.get("result"):
        click.echo(f"\n✅ Result:")
        result = op["result"]
        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, (int, float)):
                    click.echo(f"   {key}: {value}")
                else:
                    click.echo(f"   {key}: {json.dumps(value)}")
        else:
            click.echo(f"   {json.dumps(result, indent=2)}")

    if op.get("error"):
        click.echo(f"\n❌ Error: {op['error']}")

    if verbose and op.get("result"):
        click.echo(f"\n📊 Full result:")
        click.echo(json.dumps(op["result"], indent=2))


@click.group()
@click.version_option()
def cli():
    """Ultradex API CLI"""
    pass


@cli.command()
@click.option("--limit", "-l", type=int, help="Max contacts to analyze")
@click.option("--wait", "-w", type=int, default=600, help="Max seconds to wait (default: 600)")
@click.option("--key", "-k", help="Idempotency key (for deduplication)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
async def analyze_cmd(limit: Optional[int], wait: int, key: Optional[str], verbose: bool):
    """Analyze contacts"""
    config = get_config()

    try:
        async with UltradexClient(config["api_url"], config["api_key"]) as client:
            click.echo("📊 Starting analysis...")

            result = await client.analyze_contacts(
                limit=limit,
                idempotency_key=key,
                poll_timeout=wait
            )

            print_operation(result, verbose)
            click.echo()

    except TimeoutError:
        click.echo("❌ Operation timed out", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Exit(1)


@cli.command()
@click.option("--wait", "-w", type=int, default=600, help="Max seconds to wait (default: 600)")
@click.option("--key", "-k", help="Idempotency key (for deduplication)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
async def sync_cmd(wait: int, key: Optional[str], verbose: bool):
    """Sync contacts from Dex"""
    config = get_config()

    try:
        async with UltradexClient(config["api_url"], config["api_key"]) as client:
            click.echo("🔄 Starting sync...")

            result = await client.sync_contacts(
                idempotency_key=key,
                poll_timeout=wait
            )

            print_operation(result, verbose)
            click.echo()

    except TimeoutError:
        click.echo("❌ Operation timed out", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Exit(1)


@cli.command()
@click.argument("operation_id")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
async def status_cmd(operation_id: str, verbose: bool):
    """Check operation status"""
    config = get_config()

    try:
        async with UltradexClient(config["api_url"], config["api_key"]) as client:
            op = await client.get_operation(operation_id)
            print_operation(op, verbose)
            click.echo()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Exit(1)


@cli.command()
@click.argument("operation_id")
async def events_cmd(operation_id: str):
    """Show operation events"""
    config = get_config()

    try:
        async with UltradexClient(config["api_url"], config["api_key"]) as client:
            events = await client.get_operation_events(operation_id)

            click.echo(f"\n📜 Events for {operation_id}:")
            click.echo()

            for event in events:
                timestamp = format_timestamp(event.get("timestamp"))
                event_type = event.get("event_type", "unknown")

                # Icons for different event types
                icon = {
                    "operation.accepted": "📥",
                    "task.started": "▶️",
                    "task.progress": "⏳",
                    "task.completed": "✅",
                    "task.failed": "❌",
                }.get(event_type, "•")

                click.echo(f"{icon} {event_type}")
                click.echo(f"   {timestamp}")

                if event.get("payload"):
                    payload = event["payload"]
                    if isinstance(payload, dict):
                        for key, value in payload.items():
                            click.echo(f"   {key}: {value}")

            click.echo()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Exit(1)


@cli.command()
def config_cmd():
    """Show current configuration"""
    config = get_config()

    click.echo("\n⚙️  Current Configuration:")
    click.echo(f"   API URL: {config['api_url']}")
    click.echo(f"   API Key: {'Set' if config['api_key'] else 'Not set'}")
    click.echo()
    click.echo("Set via environment variables:")
    click.echo("   ULTRADEX_API_URL - API endpoint URL")
    click.echo("   ULTRADEX_API_KEY - Bearer token (optional)")
    click.echo()


@cli.command()
def health_cmd():
    """Check API health"""
    import httpx

    config = get_config()

    try:
        with httpx.Client() as client:
            response = client.get(f"{config['api_url']}/health")
            if response.status_code == 200:
                click.echo("✅ API is healthy")
            else:
                click.echo(f"⚠️  API returned {response.status_code}")
    except Exception as e:
        click.echo(f"❌ API is unreachable: {e}")
        raise click.Exit(1)


# Async wrapper for Click
def async_cmd(f):
    """Decorator to run async functions in Click commands"""
    @click.pass_context
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


# Apply async wrapper to async commands
analyze_cmd = async_cmd(analyze_cmd.callback)
analyze_cmd = click.command("analyze", help="Analyze contacts")(analyze_cmd)

sync_cmd = async_cmd(sync_cmd.callback)
sync_cmd = click.command("sync", help="Sync contacts from Dex")(sync_cmd)

status_cmd = async_cmd(status_cmd.callback)
status_cmd = click.command("status", help="Check operation status")(status_cmd)

events_cmd = async_cmd(events_cmd.callback)
events_cmd = click.command("events", help="Show operation events")(events_cmd)


if __name__ == "__main__":
    cli()
