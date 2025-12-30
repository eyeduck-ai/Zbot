#!/usr/bin/env python3
"""
Zbot Build & Release Script

Usage:
    uv run python scripts/build_release.py build              # Build EXEs only
    uv run python scripts/build_release.py release 1.2.0      # Build + release specific version
    uv run python scripts/build_release.py release --patch    # Auto-increment patch (1.2.0 → 1.2.1)
    uv run python scripts/build_release.py release --minor    # Auto-increment minor (1.2.0 → 1.3.0)
    uv run python scripts/build_release.py release --major    # Auto-increment major (1.2.0 → 2.0.0)
    uv run python scripts/build_release.py upload-launcher    # Upload launcher to dedicated release
    uv run python scripts/build_release.py upload-launcher --build  # Build + upload launcher
    uv run python scripts/build_release.py --help

Note: This script should be run on Windows for packaging.
"""
import os
import re
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"
LAUNCHER_DIR = PROJECT_ROOT / "zbot_launcher"

DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

# Output names
MAIN_APP_NAME = "Zbot_Server"  # Changed from Zbot_Main for new architecture
LAUNCHER_NAME = "Zbot"


def run_cmd(cmd: list[str], cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run command and print output."""
    print(f"  → {' '.join(cmd)}")
    # Use shell=True on Windows to properly resolve npm, git, etc.
    return subprocess.run(cmd, cwd=cwd, check=check, shell=True)


def get_latest_git_tag() -> str | None:
    """Get the latest git tag (semantic version)."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    # Fallback: list all tags and get latest
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "v*", "--sort=-v:refname"],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        if result.returncode == 0 and result.stdout.strip():
            tags = result.stdout.strip().split("\n")
            return tags[0] if tags else None
    except Exception:
        pass
    
    return None


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse version string to (major, minor, patch)."""
    # Remove 'v' prefix if present
    clean = version_str.lstrip("v")
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", clean)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    raise ValueError(f"Invalid version format: {version_str}")


def increment_version(current: str, bump_type: str) -> str:
    """
    Increment version based on bump type.
    
    Args:
        current: Current version (e.g., "v1.2.3" or "1.2.3")
        bump_type: "major", "minor", or "patch"
    
    Returns:
        New version string without 'v' prefix (e.g., "1.2.4")
    """
    major, minor, patch = parse_version(current)
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")


def get_next_version(bump_type: str) -> str:
    """Get next version based on latest git tag and bump type."""
    latest_tag = get_latest_git_tag()
    
    if latest_tag is None:
        print("  ℹ️  No existing tags found, starting from v0.1.0")
        return "0.1.0"
    
    print(f"  ℹ️  Latest tag: {latest_tag}")
    new_version = increment_version(latest_tag, bump_type)
    print(f"  ℹ️  New version: v{new_version}")
    return new_version


def clean_build():
    """Clean previous build artifacts."""
    print("\n🧹 Cleaning previous builds...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
    print("  ✓ Cleaned")


def build_frontend():
    """Build frontend with npm."""
    print("\n📦 Building frontend...")
    if not (FRONTEND_DIR / "node_modules").exists():
        run_cmd(["npm", "install"], cwd=FRONTEND_DIR)
    run_cmd(["npm", "run", "build"], cwd=FRONTEND_DIR)
    print("  ✓ Frontend built")


def build_main_app():
    """Build the main FastAPI server (Zbot_Server)."""
    print("\n🔨 Building Zbot_Server...")
    
    # Run PyInstaller from backend directory with zbot_server.spec
    # Output to ../dist (root dist)
    cmd = [
        "uv", "run", "pyinstaller",
        "--clean",
        "--distpath", "../dist",
        "--workpath", "../build",
        "zbot_server.spec"  # New spec file for server-only build
    ]
    
    print(f"  → {' '.join(cmd)}")
    
    # Execute in backend directory
    result = subprocess.run(cmd, cwd="backend", check=False)
    
    if result.returncode != 0:
        print("❌ Server build failed!")
        sys.exit(1)
        
    print("  ✓ Zbot_Server built")


def copy_assets():
    """Copy assets (icon) to dist folder."""
    print("\n🎨 Copying assets...")
    
    # Create assets directory in dist
    dest_assets = DIST_DIR / MAIN_APP_NAME / "assets"
    dest_assets.mkdir(parents=True, exist_ok=True)
    
    # Copy icon (source is logo.ico, dest is icon.ico for compatibility with run_app.py)
    # Copy icon (source is zbot_launcher/assets/icon.ico)
    icon_src = LAUNCHER_DIR / "assets" / "icon.ico"
    if icon_src.exists():
        shutil.copy(icon_src, dest_assets / "icon.ico")
        print(f"  ✓ Copied icon.ico from launcher assets")
    else:
        print(f"  ⚠️  icon.ico not found at {icon_src}")


def build_launcher():
    """Build Zbot launcher with PyInstaller using workspace dependencies."""
    print("\n🚀 Building Zbot launcher...")
    
    spec_file = LAUNCHER_DIR / "zbot.spec"
    # Use uv run from project root to use workspace dependencies
    run_cmd(["uv", "run", "pyinstaller", "--clean", str(spec_file)], cwd=PROJECT_ROOT)
    
    # Move launcher to main dist (output is in project root dist/)
    launcher_exe = DIST_DIR / f"{LAUNCHER_NAME}.exe"
    if not launcher_exe.exists():
        # Check if it's in LAUNCHER_DIR/dist (fallback)
        launcher_exe = LAUNCHER_DIR / "dist" / f"{LAUNCHER_NAME}.exe"
        if launcher_exe.exists():
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(launcher_exe, DIST_DIR / f"{LAUNCHER_NAME}.exe")
    
    print("  ✓ Launcher built")


def create_release_zip(version: str) -> Path:
    """Create release ZIP for Zbot_Server."""
    print("\n📁 Creating release ZIP...")
    
    main_app_dir = DIST_DIR / MAIN_APP_NAME
    if not main_app_dir.exists():
        raise FileNotFoundError(f"Zbot_Server not found at {main_app_dir}")
    
    zip_name = f"{MAIN_APP_NAME}_v{version}_win64"
    zip_path = DIST_DIR / zip_name
    
    shutil.make_archive(str(zip_path), "zip", DIST_DIR, MAIN_APP_NAME)
    
    final_zip = DIST_DIR / f"{zip_name}.zip"
    print(f"  ✓ Created: {final_zip}")
    return final_zip


def create_version_json(version: str):
    """Create version.json for distribution."""
    version_file = DIST_DIR / "version.json"
    data = {
        "app_version": version,
        "built_at": datetime.now().isoformat(),
    }
    with open(version_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ Created: {version_file}")


def git_tag_and_push(version: str):
    """Create git tag and push."""
    print(f"\n🏷️  Creating git tag v{version}...")
    
    tag = f"v{version}"
    
    # Check if tag exists
    result = subprocess.run(["git", "tag", "-l", tag], capture_output=True, text=True)
    if tag in result.stdout:
        print(f"  ⚠️  Tag {tag} already exists, skipping...")
        return
    
    run_cmd(["git", "tag", "-a", tag, "-m", f"Release {tag}"], cwd=PROJECT_ROOT)
    run_cmd(["git", "push", "origin", tag], cwd=PROJECT_ROOT)
    print(f"  ✓ Tag {tag} pushed")


def create_github_release(version: str, zip_path: Path):
    """Create GitHub release using gh CLI."""
    print(f"\n🚀 Creating GitHub release v{version}...")
    
    # Check if gh CLI is available
    if not shutil.which("gh"):
        print("  ⚠️  GitHub CLI (gh) not installed or not found")
        print("  ℹ️  Install: https://cli.github.com/")
        print(f"  ℹ️  Manual upload: {zip_path}")
        return
    
    tag = f"v{version}"
    run_cmd([
        "gh", "release", "create", tag,
        str(zip_path),
        "--title", f"Zbot v{version}",
        "--notes", f"Release v{version}",
    ], cwd=PROJECT_ROOT)
    
    print(f"  ✓ GitHub release created")


def upload_to_gdrive(zip_path: Path) -> str | None:
    """
    Upload to Google Drive using rclone.
    Returns the destination path if successful.
    """
    print(f"\n☁️  Uploading to Google Drive...")
    
    # Check if rclone is available
    if not shutil.which("rclone"):
        print("  ⚠️  Google Drive upload skipped (rclone not installed or not found)")
        print(f"  ℹ️  Manually upload: {zip_path}")
        return None
    
    # Assumes rclone remote named "gdrive" is configured
    dest = f"gdrive:Zbot/releases/{zip_path.name}"
    try:
        run_cmd(["rclone", "copy", str(zip_path), dest])
        print(f"  ✓ Uploaded to Google Drive: {dest}")
        return dest
    except subprocess.CalledProcessError:
        print("  ⚠️  rclone upload failed")
        print(f"  ℹ️  Manually upload: {zip_path}")
        return None


def upload_launcher_release():
    """Upload launcher to a dedicated GitHub release with stable URL."""
    print("\n🚀 Uploading launcher to GitHub...")
    
    launcher_exe = DIST_DIR / f"{LAUNCHER_NAME}.exe"
    if not launcher_exe.exists():
        # Try from launcher build directory
        launcher_exe = LAUNCHER_DIR / "dist" / f"{LAUNCHER_NAME}.exe"
    
    if not launcher_exe.exists():
        print("  ❌ Launcher not found. Run 'build' first.")
        return False
    
    # Check if gh CLI is available
    if not shutil.which("gh"):
        print("  ❌ GitHub CLI (gh) not installed or not found")
        print("  ℹ️  Install: https://cli.github.com/")
        return False
    
    tag = "launcher"
    
    # Check if release exists
    result = subprocess.run(
        ["gh", "release", "view", tag],
        capture_output=True, cwd=PROJECT_ROOT
    )
    
    if result.returncode == 0:
        # Release exists, update it
        print(f"  ℹ️  Updating existing '{tag}' release...")
        run_cmd([
            "gh", "release", "upload", tag,
            str(launcher_exe),
            "--clobber"
        ], cwd=PROJECT_ROOT)
    else:
        # Create new release
        print(f"  ℹ️  Creating new '{tag}' release...")
        run_cmd([
            "gh", "release", "create", tag,
            str(launcher_exe),
            "--title", "Zbot Launcher",
            "--notes", "下載此檔案啟動 Zbot，會自動下載並更新主程式。\n\n⚠️ 此 Release 專門存放 Launcher，請勿刪除。",
        ], cwd=PROJECT_ROOT)
    
    print("  ✓ Launcher uploaded")
    print(f"  ℹ️  Download URL: https://github.com/<owner>/<repo>/releases/download/launcher/{LAUNCHER_NAME}.exe")
    return True


def cmd_upload_launcher(args):
    """Upload launcher command."""
    if args.build:
        print("\n🔨 Building launcher first...")
        build_launcher()
    
    upload_launcher_release()
    print("\n✅ Launcher upload complete!")


def cmd_build(args):
    """Build command.
    
    With --only option, can build specific components:
    - frontend: Build React frontend only
    - server: Build Zbot_Server (backend) only  
    - launcher: Build Zbot.exe (launcher) only
    - all (default): Build everything
    """
    target = getattr(args, 'only', 'all') or 'all'
    
    if target == 'all':
        clean_build()
        build_frontend()
        build_main_app()
        copy_assets()
        build_launcher()
        print("\n✅ Build complete! (all)")
    elif target == 'frontend':
        build_frontend()
        print("\n✅ Frontend build complete!")
    elif target == 'server':
        build_main_app()
        copy_assets()
        print("\n✅ Server build complete!")
    elif target == 'launcher':
        build_launcher()
        print("\n✅ Launcher build complete!")
    else:
        print(f"❌ Unknown target: {target}")
        print("   Valid options: all, frontend, server, launcher")
        return
    
    print(f"   Output: {DIST_DIR}")


def cmd_release(args):
    """Release command."""
    # Determine version
    if args.version:
        version = args.version.lstrip("v")
    elif args.bump:
        print(f"\n📊 Auto-increment version ({args.bump})...")
        version = get_next_version(args.bump)
    else:
        print("Error: Please specify version or use --major/--minor/--patch")
        sys.exit(1)
    
    print(f"\n🎯 Building release v{version}...")
    
    # Confirmation
    confirm = input(f"   Proceed with v{version}? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("   Cancelled.")
        return
    
    # Build everything
    clean_build()
    build_frontend()
    build_main_app()
    copy_assets()
    build_launcher()
    
    # Create release artifacts
    zip_path = create_release_zip(version)
    create_version_json(version)
    
    # Git operations
    if args.tag:
        git_tag_and_push(version)
    
    # Upload to GitHub
    if args.github:
        create_github_release(version, zip_path)
        # Also upload launcher to dedicated release
        upload_launcher_release()
    
    # Upload to Google Drive
    if args.gdrive:
        upload_to_gdrive(zip_path)
    
    print("\n" + "=" * 50)
    print(f"✅ Release v{version} complete!")
    print(f"   📁 ZIP: {zip_path}")
    print(f"   🚀 Launcher: {DIST_DIR / f'{LAUNCHER_NAME}.exe'}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Zbot Build & Release Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build EXEs only")
    build_parser.add_argument("--only", choices=["all", "frontend", "server", "launcher"],
                              default="all", help="Build specific component only")
    build_parser.set_defaults(func=cmd_build)
    
    # Release command
    release_parser = subparsers.add_parser("release", help="Build + tag + release")
    
    # Version specification (mutually exclusive)
    version_group = release_parser.add_mutually_exclusive_group()
    version_group.add_argument("version", nargs="?", default=None,
                               help="Version number (e.g., 1.2.0)")
    version_group.add_argument("--major", dest="bump", action="store_const", const="major",
                               help="Bump major version (X.0.0)")
    version_group.add_argument("--minor", dest="bump", action="store_const", const="minor",
                               help="Bump minor version (x.X.0)")
    version_group.add_argument("--patch", dest="bump", action="store_const", const="patch",
                               help="Bump patch version (x.x.X)")
    
    # Optional flags
    release_parser.add_argument("--no-tag", dest="tag", action="store_false", 
                                help="Skip git tagging")
    release_parser.add_argument("--no-github", dest="github", action="store_false",
                                help="Skip GitHub release")
    release_parser.add_argument("--no-gdrive", dest="gdrive", action="store_false",
                                help="Skip Google Drive upload")
    release_parser.set_defaults(func=cmd_release, tag=True, github=True, gdrive=True, bump=None)
    
    # Upload-launcher command
    upload_parser = subparsers.add_parser("upload-launcher", help="Upload launcher to dedicated GitHub release")
    upload_parser.add_argument("--build", action="store_true",
                               help="Build launcher before uploading")
    upload_parser.set_defaults(func=cmd_upload_launcher, build=False)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
