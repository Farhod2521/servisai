#!/usr/bin/env bash
# Obunalar boti — Linux / macOS uchun bir martalik sozlash
set -e

echo "📦 Kutubxonalar o'rnatilmoqda..."
python3 -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "📝 .env fayl yaratildi."
  echo "   Endi uni oching va BOT_TOKEN ni to'ldiring:"
  echo "      nano .env"
  echo ""
  echo "   To'ldirgach qayta ishga tushiring:  ./setup.sh"
  exit 0
fi

if ! grep -q "^BOT_TOKEN=.\+" .env; then
  echo ""
  echo "❌ .env ichida BOT_TOKEN bo'sh. @BotFather dan token oling va yozing."
  exit 1
fi

echo "🗄  Namuna ma'lumot qo'shilmoqda..."
python3 seed.py || true

echo ""
echo "🚀 Bot ishga tushmoqda... (to'xtatish uchun Ctrl+C)"
python3 bot.py
