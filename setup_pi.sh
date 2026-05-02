#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/raspi/2002"
VENV_PATH="$PROJECT_ROOT/venv"
WHISPER_DIR="$PROJECT_ROOT/whisper.cpp"
PIPER_DIR="$PROJECT_ROOT/piper/voices"

sudo apt-get update
sudo apt-get install -y \
  build-essential \
  cmake \
  git \
  wget \
  alsa-utils \
  libasound2-dev \
  python3-pip \
  python3-venv

mkdir -p "$PROJECT_ROOT" "$PROJECT_ROOT/config" "$PROJECT_ROOT/audio" "$PROJECT_ROOT/brain" "$PROJECT_ROOT/senses" "$PIPER_DIR"

if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
fi

"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"

if [ ! -d "$WHISPER_DIR" ]; then
  git clone https://github.com/ggerganov/whisper.cpp "$WHISPER_DIR"
fi

( cd "$WHISPER_DIR" && make -j"$(nproc)" )

if [ ! -f "$WHISPER_DIR/models/ggml-base.en.bin" ]; then
  ( cd "$WHISPER_DIR" && bash ./models/download-ggml-model.sh base.en )
fi

VOICE_MODEL="$PIPER_DIR/en_US-hfc_female-medium.onnx"
VOICE_CONFIG="$PIPER_DIR/en_US-hfc_female-medium.onnx.json"

if [ ! -f "$VOICE_MODEL" ]; then
  wget -O "$VOICE_MODEL" \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx
fi

if [ ! -f "$VOICE_CONFIG" ]; then
  wget -O "$VOICE_CONFIG" \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json
fi

echo "Setup complete. Activate with: source $VENV_PATH/bin/activate"
