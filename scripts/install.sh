#!/usr/bin/env bash
# Netrr installer: creates a venv and installs the package with the right
# platform extra. Run from anywhere:  bash scripts/install.sh
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_DIR}/venv"
PYTHON="${PYTHON:-python3}"

cd "${REPO_DIR}"

# --- Detect platform ------------------------------------------------------
detect_platform() {
    local model=""
    if [ -r /proc/device-tree/model ]; then
        model="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)"
    fi
    if [ -z "${model}" ] && [ -r /proc/cpuinfo ]; then
        model="$(grep -i 'raspberry pi' /proc/cpuinfo 2>/dev/null | head -n 1 || true)"
    fi

    case "${model}" in
        *"Raspberry Pi"*|*"raspberry pi"*) echo "raspberry_pi"; return ;;
        *NVIDIA*|*Jetson*)                  echo "jetson";       return ;;
    esac
    if [ -f /etc/nv_tegra_release ]; then
        echo "jetson"; return
    fi
    echo "other"
}

PLATFORM="$(detect_platform)"

echo "============================================================"
echo "       NETRR INSTALLER"
echo "============================================================"
echo "Repository : ${REPO_DIR}"
echo "Platform   : ${PLATFORM}"
echo "Python     : $("${PYTHON}" --version 2>&1)"
echo

# --- Virtual environment --------------------------------------------------
if [ ! -d "${VENV_DIR}" ]; then
    echo ">> Creating virtual environment in ${VENV_DIR}"
    # On Raspberry Pi, picamera2 comes from apt; let the venv see system packages.
    if [ "${PLATFORM}" = "raspberry_pi" ]; then
        "${PYTHON}" -m venv --system-site-packages "${VENV_DIR}"
    else
        "${PYTHON}" -m venv "${VENV_DIR}"
    fi
else
    echo ">> Reusing existing virtual environment in ${VENV_DIR}"
fi

VENV_PIP="${VENV_DIR}/bin/pip"

echo ">> Upgrading pip"
"${VENV_PIP}" install --upgrade pip

echo ">> Installing netrr (editable)"
"${VENV_PIP}" install -e .

case "${PLATFORM}" in
    raspberry_pi) EXTRA="pi" ;;
    jetson)       EXTRA="jetson" ;;
    *)            EXTRA="dev" ;;
esac

echo ">> Installing platform extra: .[${EXTRA}]"
"${VENV_PIP}" install -e ".[${EXTRA}]"

# --- Next steps -----------------------------------------------------------
echo
echo "============================================================"
echo "       INSTALL COMPLETE"
echo "============================================================"
echo "Next steps:"
echo "  source \"${VENV_DIR}/bin/activate\""
if [ ! -f "${REPO_DIR}/.env" ]; then
    echo "  cp .env.example .env      # then fill in GEMINI_API_KEY etc."
fi
echo "  netrr-doctor              # check camera, audio, deps and API keys"
echo "  netrr --mode all          # start the glasses"
