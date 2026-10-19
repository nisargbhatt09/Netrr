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

# --- Jetson: system OpenCV -----------------------------------------------
# The Jetson CSI camera is read through a GStreamer pipeline. The pip wheels
# (opencv-python, opencv-python-headless) are built without GStreamer; the
# JetPack system package python3-opencv is built with it. So on a Jetson we
# take OpenCV (and numpy, which it is linked against) from apt and keep pip
# from installing a wheel that would shadow it.
if [ "${PLATFORM}" = "jetson" ]; then
    echo ">> Installing JetPack OpenCV and numpy from apt (needs sudo)"
    sudo apt-get update
    sudo apt-get install -y python3-opencv python3-numpy
fi

# --- Virtual environment --------------------------------------------------
if [ ! -d "${VENV_DIR}" ]; then
    echo ">> Creating virtual environment in ${VENV_DIR}"
    # On Raspberry Pi picamera2 comes from apt, on Jetson the GStreamer-enabled
    # OpenCV does; let the venv see system packages on both.
    if [ "${PLATFORM}" = "raspberry_pi" ] || [ "${PLATFORM}" = "jetson" ]; then
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

if [ "${PLATFORM}" = "jetson" ]; then
    # Install the project without its declared dependencies, then add the
    # runtime dependencies by hand, leaving out opencv-python-headless and
    # numpy (both come from apt above) and ultralytics (it pulls in a torch
    # wheel that does not match JetPack; install NVIDIA's torch separately
    # and then `pip install --no-deps ultralytics` if object detection is
    # wanted). This keeps a pip wheel from shadowing the system OpenCV.
    echo ">> Installing netrr (editable, without pip dependencies)"
    "${VENV_PIP}" install --no-deps -e .

    echo ">> Installing runtime dependencies (except opencv, numpy, ultralytics)"
    "${VENV_PIP}" install \
        Pillow \
        requests \
        SpeechRecognition \
        python-dotenv \
        edge-tts \
        psutil \
        google-genai

    echo ">> Installing platform extra: jetson-stats"
    "${VENV_PIP}" install jetson-stats

    echo ">> Checking that the venv sees the GStreamer-enabled OpenCV"
    if ! "${VENV_DIR}/bin/python" -c 'import cv2, sys; from netrr.platform import opencv_has_gstreamer; sys.exit(0 if opencv_has_gstreamer(cv2.getBuildInformation()) else 1)'; then
        echo "WARNING: the OpenCV visible in the venv has no GStreamer support, so the CSI camera will not open."
        echo "         Make sure no opencv-python wheel is installed in the venv (pip uninstall opencv-python opencv-python-headless)."
    fi
else
    echo ">> Installing netrr (editable)"
    "${VENV_PIP}" install -e .

    case "${PLATFORM}" in
        raspberry_pi) EXTRA="pi" ;;
        *)            EXTRA="dev" ;;
    esac

    echo ">> Installing platform extra: .[${EXTRA}]"
    "${VENV_PIP}" install -e ".[${EXTRA}]"
fi

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
