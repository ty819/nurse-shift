#!/bin/bash
# Render Free プラン用のビルドスクリプト

# システムパッケージのインストール（日本語フォント対応）
apt-get update
apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libfreetype6 \
    libfreetype6-dev

# Pythonパッケージのインストール
pip install --upgrade pip
pip install -r requirements.txt
