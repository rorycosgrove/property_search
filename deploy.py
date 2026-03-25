#!/usr/bin/env python3
"""
Interactive setup & deploy script for Irish Property Research Dashboard.

Usage:
    python deploy.py              Full guided setup + deploy
    python deploy.py --check      Check prerequisites only
    python deploy.py --deploy     Skip install, deploy only
    python deploy.py --local      Set up local dev environment only
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent
INFRA_DIR = ROOT / "infra"
WEB_DIR = ROOT / "web"
MIN_PYTHON = (3, 12)
MIN_NODE = 20
AWS_REGION_DEFAULT = "eu-west-1"

COLOURS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _colour(text: str, colour: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{COLOURS.get(colour, '')}{text}{COLOURS['reset']}"


def info(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def error(msg: str) -> None:
    print(f"  [ERROR] {msg}")


def heading(msg: str) -> None:
    print(f"\n{_colour(f'-- {msg} ', 'cyan')}" + "-" * max(0, 60 - len(msg)))


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or default


def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"  {prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def run(cmd: list[str], cwd: Path | None = None, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess, streaming output unless capture=True."""
    kwargs: dict = {"cwd": cwd or ROOT, "check": check}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    else:
        kwargs["stdin"] = sys.stdin
        kwargs["stdout"] = sys.stdout
        kwargs["stderr"] = sys.stderr
    return subprocess.run(cmd, **kwargs)


def cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def get_version(cmd: list[str]) -> str:
    try:
        result = run(cmd, capture=True, check=False)
        return result.stdout.strip()
    except FileNotFoundError:
        return ""


# ── Prerequisite Checks ──────────────────────────────────────────────────────


def check_python() -> bool:
    v = sys.version_info
    ok = v >= MIN_PYTHON
    label = f"Python {v.major}.{v.minor}.{v.micro}"
    if ok:
        info(label)
    else:
        error(f"{label} — need {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+")
    return ok


def check_node() -> bool:
    ver = get_version(["node", "--version"])
    if not ver:
        error("Node.js not found — install Node.js 20+ from https://nodejs.org")
        return False
    match = re.match(r"v?(\d+)", ver)
    major = int(match.group(1)) if match else 0
    if major >= MIN_NODE:
        info(f"Node.js {ver}")
        return True
    error(f"Node.js {ver} — need v{MIN_NODE}+")
    return False


def check_npm() -> bool:
    if cmd_exists("npm"):
        info(f"npm {get_version(['npm', '--version'])}")
        return True
    error("npm not found")
    return False


def check_aws_cli() -> bool:
    ver = get_version(["aws", "--version"])
    if ver:
        info(f"AWS CLI: {ver.split()[0]}")
        return True
    error("AWS CLI not found — install from https://aws.amazon.com/cli/")
    return False


def check_aws_credentials() -> bool:
    try:
        result = run(["aws", "sts", "get-caller-identity"], capture=True, check=False)
    except FileNotFoundError:
        error("AWS CLI not available")
        return False
    if result.returncode == 0:
        identity = json.loads(result.stdout)
        info(f"AWS Account: {identity['Account']} ({identity.get('Arn', '')})")
        return True
    error("AWS credentials not configured — run: aws configure")
    return False


def check_docker() -> bool:
    if cmd_exists("docker"):
        ver = get_version(["docker", "--version"])
        info(f"Docker: {ver}")
        return True
    warn("Docker not found — needed only for local dev (PostgreSQL)")
    return True  # not required for AWS deploy


def check_prerequisites(require_aws: bool = True) -> bool:
    heading("Checking Prerequisites")
    results = [check_python(), check_node(), check_npm()]
    if require_aws:
        aws_ok = check_aws_cli()
        results.append(aws_ok)
        if aws_ok:
            results.append(check_aws_credentials())
        else:
            results.append(False)
    check_docker()
    return all(results)


# ── Installation ──────────────────────────────────────────────────────────────


def install_python_deps() -> bool:
    heading("Installing Python Dependencies")
    try:
        run([sys.executable, "-m", "pip", "install", "-e", ".[dev]", "-q"])
        info("Python dependencies installed")
        return True
    except subprocess.CalledProcessError:
        error("Failed to install Python dependencies")
        return False


def install_cdk_deps() -> bool:
    heading("Installing CDK Dependencies")
    if not (INFRA_DIR / "package.json").exists():
        error("infra/package.json not found")
        return False
    try:
        run(["npm.cmd", "install"], cwd=INFRA_DIR)
        info("CDK dependencies installed")
        return True
    except subprocess.CalledProcessError:
        error("Failed to install CDK dependencies — try: cd infra && npm install")
        return False


def install_frontend_deps() -> bool:
    heading("Installing Frontend Dependencies")
    if not (WEB_DIR / "package.json").exists():
        error("web/package.json not found")
        return False
    try:
        run(["npm.cmd", "install"], cwd=WEB_DIR)
        info("Frontend dependencies installed")
        return True
    except subprocess.CalledProcessError:
        error("Failed to install frontend dependencies")
        return False


# ── AWS Configuration ─────────────────────────────────────────────────────────


def get_aws_region() -> str:
    result = run(["aws", "configure", "get", "region"], capture=True, check=False)
    configured = result.stdout.strip()
    if configured:
        return configured
    return AWS_REGION_DEFAULT


def enable_bedrock_reminder() -> None:
    heading("Amazon Bedrock Setup")
    print(textwrap.dedent("""\
        The app uses Amazon Bedrock for AI features. You must enable model access
        manually in the AWS Console:

          1. Go to: https://console.aws.amazon.com/bedrock
          2. Navigate to Model access → Manage model access
          3. Enable: Amazon Titan Text Express, Titan Text Lite, Nova Micro
          4. Click Save changes

        AI features will work once models are enabled. The app functions
        without them, but enrichment endpoints will return errors.
    """))
    input("  Press Enter when ready to continue...")


# ── CDK Deploy ────────────────────────────────────────────────────────────────


def cdk_bootstrap(region: str, account: str) -> bool:
    heading("Bootstrapping CDK")
    info(f"Region: {region}, Account: {account}")
    try:
        run(["npx", "cdk", "bootstrap", f"aws://{account}/{region}"], cwd=INFRA_DIR)
        info("CDK bootstrap complete")
        return True
    except subprocess.CalledProcessError:
        error("CDK bootstrap failed")
        return False


def cdk_synth() -> bool:
    heading("Synthesizing CloudFormation Templates")
    try:
        run(["npx", "cdk", "synth"], cwd=INFRA_DIR)
        info("Synth complete — templates look valid")
        return True
    except subprocess.CalledProcessError:
        error("CDK synth failed — check TypeScript errors above")
        return False


def cdk_deploy() -> bool:
    heading("Deploying All Stacks")
    print("  This deploys 7 stacks: VPC → Secrets → Database → Workers → API → Scheduler → Frontend")
    print("  First deployment takes ~10-15 minutes (RDS creation is slow).\n")
    try:
        run(["npx", "cdk", "deploy", "--all", "--require-approval", "broadening", "--outputs-file", str(ROOT / "cdk-outputs.json")], cwd=INFRA_DIR)
        info("All stacks deployed successfully")
        return True
    except subprocess.CalledProcessError:
        error("CDK deploy failed — check errors above")
        return False


def get_api_url() -> str:
    outputs_file = ROOT / "cdk-outputs.json"
    if outputs_file.exists():
        try:
            outputs = json.loads(outputs_file.read_text())
            for stack_name, stack_outputs in outputs.items():
                for key, value in stack_outputs.items():
                    if "apiurl" in key.lower() or "ApiUrl" in key:
                        return value
        except (json.JSONDecodeError, KeyError):
            pass
    return ""


def get_stack_output(*name_fragments: str) -> str:
    outputs_file = ROOT / "cdk-outputs.json"
    if not outputs_file.exists():
        return ""

    try:
        outputs = json.loads(outputs_file.read_text())
    except (json.JSONDecodeError, OSError):
        return ""

    targets = tuple(fragment.lower() for fragment in name_fragments)
    for stack_outputs in outputs.values():
        for key, value in stack_outputs.items():
            lowered = key.lower()
            if all(fragment in lowered for fragment in targets):
                return str(value)
    return ""


def run_migrations(api_url: str) -> bool:
    heading("Running Database Migrations")
    db_endpoint = get_stack_output("db", "endpoint")
    db_name = get_stack_output("db", "name") or "propertysearch"
    secret_arn = get_stack_output("secret", "arn")
    if api_url:
        info(f"API URL: {api_url}")
    if db_endpoint:
        info(f"RDS endpoint: {db_endpoint}")
    if secret_arn:
        info(f"DB secret ARN: {secret_arn}")

    warn("Automatic remote migrations are not available in this script.")
    print(textwrap.dedent("""\
        The deployed RDS instance is private and the public API does not expose a
        migration endpoint. Run Alembic from an environment with network access
        to the database, then return to source/grant seeding.

        Recommended command:
            uv run alembic upgrade head

        Typical options:
          - a shell inside the VPC
          - a bastion or SSM port-forward into the VPC
          - any trusted environment that can reach the private RDS endpoint
    """))

    if db_endpoint and secret_arn:
        print(textwrap.dedent(f"""\
            Example (PowerShell) to inspect DB credentials from Secrets Manager:
              aws secretsmanager get-secret-value --secret-id {secret_arn} --query SecretString --output text

            Connection target summary:
              host={db_endpoint}
              port=5432
              db={db_name}
        """))

    return confirm("Have you already run migrations in a VPC-accessible environment?", default=False)


def _load_seed_defaults() -> tuple[list[dict], list[dict]]:
    from scripts.seed import DEFAULT_GRANTS, DEFAULT_SOURCES

    return [dict(item) for item in DEFAULT_SOURCES], [dict(item) for item in DEFAULT_GRANTS]


def seed_sources(api_url: str) -> bool:
    heading("Seeding Default Sources")
    if not api_url:
        warn("API URL not available. Seed manually after deployment.")
        return True

    sources, _ = _load_seed_defaults()

    sources_url = f"{api_url}/api/v1/sources"
    import urllib.request
    import urllib.error

    seeded = 0
    for source in sources:
        try:
            data = json.dumps(source).encode()
            req = urllib.request.Request(
                sources_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                seeded += 1
        except urllib.error.HTTPError as e:
            if e.code == 409:
                info(f"Already exists: {source['name']}")
            else:
                warn(f"Failed to seed {source['name']}: {e.code}")
        except Exception as e:
            warn(f"Error seeding {source['name']}: {e}")

    info(f"Seeded {seeded}/{len(sources)} sources")
    return True


def seed_grants(api_url: str) -> bool:
    heading("Seeding Default Grants")
    if not api_url:
        warn("API URL not available. Seed manually after deployment.")
        return True

    _, grants = _load_seed_defaults()

    grants_url = f"{api_url}/api/v1/grants"
    import urllib.request
    import urllib.error

    seeded = 0
    for grant in grants:
        try:
            data = json.dumps(grant).encode()
            req = urllib.request.Request(
                grants_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30):
                seeded += 1
        except urllib.error.HTTPError as e:
            if e.code == 409:
                info(f"Already exists: {grant['code']}")
            else:
                warn(f"Failed to seed {grant['code']}: {e.code}")
        except Exception as e:
            warn(f"Error seeding {grant['code']}: {e}")

    info(f"Seeded {seeded}/{len(grants)} grants")
    return True


# ── Local Development Setup ───────────────────────────────────────────────────


def setup_local_env() -> None:
    heading("Local Development Setup")

    env_file = ROOT / ".env"
    if not env_file.exists():
        env_example = ROOT / ".env.example"
        if env_example.exists():
            shutil.copy(env_example, env_file)
            info("Created .env from .env.example")
        else:
            warn("No .env.example found — create .env manually")
    else:
        info(".env already exists")

    if cmd_exists("docker"):
        if confirm("Start local PostgreSQL with Docker Compose?"):
            try:
                run(["docker", "compose", "up", "-d"])
                info("PostgreSQL started")
            except subprocess.CalledProcessError:
                warn("docker compose up failed — start it manually")

        heading("Running Local Migrations")
        try:
            run([sys.executable, "-m", "alembic", "upgrade", "head"])
            info("Migrations complete")
        except subprocess.CalledProcessError:
            warn("Migration failed — is PostgreSQL running?")

        if confirm("Seed default sources?"):
            try:
                run([sys.executable, "scripts/seed.py"])
                info("Sources and grants seeded")
            except subprocess.CalledProcessError:
                warn("Seeding failed")
    else:
        warn("Docker not installed — cannot start local PostgreSQL")

    heading("Ready for Local Development")
    print(textwrap.dedent("""\
        Start the API:
            uvicorn apps.api.main:app --reload --port 8000

        Start the frontend (in another terminal):
            cd web && npm run dev

        Open: http://localhost:3000
    """))


# ── Main Workflows ────────────────────────────────────────────────────────────


def full_deploy() -> None:
    print(_colour("\n╔══════════════════════════════════════════════════════════╗", "cyan"))
    print(_colour("║   Irish Property Research Dashboard — AWS Deploy Setup   ║", "cyan"))
    print(_colour("╚══════════════════════════════════════════════════════════╝\n", "cyan"))

    # Prerequisites
    if not check_prerequisites(require_aws=True):
        print(f"\n{_colour('Fix the issues above and re-run this script.', 'red')}")
        sys.exit(1)

    # Region
    heading("AWS Configuration")
    detected_region = get_aws_region()
    region = ask("AWS region", detected_region)

    identity = json.loads(
        run(["aws", "sts", "get-caller-identity"], capture=True).stdout
    )
    account = identity["Account"]
    info(f"Deploying to account {account} in {region}")

    os.environ["CDK_DEFAULT_ACCOUNT"] = account
    os.environ["CDK_DEFAULT_REGION"] = region

    # Install
    if not install_python_deps():
        sys.exit(1)
    if not install_cdk_deps():
        sys.exit(1)
    if not install_frontend_deps():
        sys.exit(1)

    # Bedrock reminder
    enable_bedrock_reminder()

    # Bootstrap CDK
    if not cdk_bootstrap(region, account):
        sys.exit(1)

    # Synth first to catch errors
    if not cdk_synth():
        sys.exit(1)

    # Deploy
    if not confirm("Deploy all 7 stacks to AWS?"):
        print("  Aborted.")
        sys.exit(0)

    if not cdk_deploy():
        sys.exit(1)

    # Post-deploy
    api_url = get_api_url()
    if api_url:
        info(f"API Gateway URL: {api_url}")
    else:
        warn("Could not read API URL from cdk-outputs.json")
        api_url = ask("Enter the API Gateway URL (from CDK output above)")

    migrations_ready = run_migrations(api_url)

    if migrations_ready and confirm("Seed default property sources?"):
        seed_sources(api_url)
        seed_grants(api_url)
    elif not migrations_ready:
        warn("Skipping API seeding until database migrations have been completed.")

    # Summary
    heading("Deployment Complete!")
    print(textwrap.dedent(f"""\
        {_colour('Your dashboard is live.', 'green')}

        API URL:       {api_url or '(check CDK outputs)'}
        Swagger docs:  {api_url + '/docs' if api_url else '(api-url/docs)'}

        Next steps:
          1. Connect Amplify to your Git repo in the AWS Console
          2. Enable Bedrock models if you haven't already
             3. Run database migrations from a VPC-accessible environment
             4. Seed sources and grants after migrations complete
             5. Wait for the first scheduled scrape (~6 hours) or trigger manually:
                 curl -X POST {api_url}/api/v1/sources/trigger-all

        Useful commands:
          make diff       Preview infrastructure changes
          make deploy     Re-deploy after code changes
          make destroy    Tear down all AWS resources
    """))


def deploy_only() -> None:
    heading("Deploy Only Mode")
    if not check_prerequisites(require_aws=True):
        sys.exit(1)

    region = get_aws_region()
    identity = json.loads(
        run(["aws", "sts", "get-caller-identity"], capture=True).stdout
    )
    account = identity["Account"]
    os.environ["CDK_DEFAULT_ACCOUNT"] = account
    os.environ["CDK_DEFAULT_REGION"] = region

    if not cdk_synth():
        sys.exit(1)
    if not cdk_deploy():
        sys.exit(1)

    api_url = get_api_url()
    if api_url:
        info(f"API URL: {api_url}")
    migrations_ready = run_migrations(api_url)
    if not migrations_ready:
        warn("Automatic seeding remains blocked until migrations are completed.")
    info("Done")


def check_only() -> None:
    ok = check_prerequisites(require_aws=True)
    if ok:
        print(f"\n{_colour('All prerequisites met. Run: python deploy.py', 'green')}")
    else:
        print(f"\n{_colour('Some prerequisites are missing.', 'red')}")
        sys.exit(1)


# ── Entry Point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy Irish Property Research Dashboard")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Check prerequisites only")
    group.add_argument("--deploy", action="store_true", help="Deploy only (skip install)")
    group.add_argument("--local", action="store_true", help="Set up local dev environment")
    args = parser.parse_args()

    try:
        if args.check:
            check_only()
        elif args.deploy:
            deploy_only()
        elif args.local:
            if not check_prerequisites(require_aws=False):
                sys.exit(1)
            install_python_deps()
            install_frontend_deps()
            setup_local_env()
        else:
            full_deploy()
    except KeyboardInterrupt:
        print(f"\n\n{_colour('Cancelled.', 'yellow')}")
        sys.exit(130)


if __name__ == "__main__":
    main()
