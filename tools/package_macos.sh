#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/macos"
PYINSTALLER_DIST="$ROOT_DIR/dist/StudyBuddyServer"
PYINSTALLER_BUILD="$ROOT_DIR/build/pyinstaller"
ARCH="$(uname -m)"
PACKAGE_NAME="StudyBuddy-macOS-${ARCH}"
PACKAGE_DIR="$BUILD_DIR/$PACKAGE_NAME"

rm -rf "$BUILD_DIR" "$PYINSTALLER_DIST" "$PYINSTALLER_BUILD" "$ROOT_DIR/dist"
mkdir -p "$BUILD_DIR"

echo "[1/4] Build frontend dist"
npm ci --prefix "$ROOT_DIR/frontend"
npm run build --prefix "$ROOT_DIR/frontend"

echo "[2/4] Install backend build dependencies"
python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/backend/requirements.txt" pyinstaller

echo "[3/4] Build macOS backend binary"
pyinstaller \
  "$ROOT_DIR/backend/server_entry.py" \
  --name StudyBuddyServer \
  --onedir \
  --clean \
  --noconfirm \
  --distpath "$ROOT_DIR/dist" \
  --workpath "$PYINSTALLER_BUILD" \
  --paths "$ROOT_DIR/backend" \
  --collect-all fitz \
  --collect-all pymupdf \
  --collect-all fastapi \
  --collect-all starlette \
  --collect-all uvicorn \
  --collect-all openai

echo "[4/4] Assemble distributable package"
mkdir -p "$PACKAGE_DIR"
cp -R "$PYINSTALLER_DIST/." "$PACKAGE_DIR/"
mkdir -p "$PACKAGE_DIR/frontend"
cp -R "$ROOT_DIR/frontend/dist" "$PACKAGE_DIR/frontend/"
mkdir -p \
  "$PACKAGE_DIR/AI伴学数据/uploads" \
  "$PACKAGE_DIR/AI伴学数据/users" \
  "$PACKAGE_DIR/AI伴学数据/shared" \
  "$PACKAGE_DIR/AI伴学数据/memory"
cp "$ROOT_DIR/scripts/macos/run_mac.command" "$PACKAGE_DIR/"
cp "$ROOT_DIR/scripts/macos/stop_mac.command" "$PACKAGE_DIR/"
cp "$ROOT_DIR/docs/macOS-actions-build.md" "$PACKAGE_DIR/README-macOS.md"
chmod +x "$PACKAGE_DIR/run_mac.command" "$PACKAGE_DIR/stop_mac.command" "$PACKAGE_DIR/StudyBuddyServer"

(
  cd "$BUILD_DIR"
  rm -f "${PACKAGE_NAME}.zip"
  zip -qry "${PACKAGE_NAME}.zip" "$PACKAGE_NAME"
)

echo "Package ready: $BUILD_DIR/${PACKAGE_NAME}.zip"
