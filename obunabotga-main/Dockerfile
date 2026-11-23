FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# telethon'ning pyaes paketi yangi setuptools bilan yig'ilmaydi — avval eskiroq setuptools bilan o'rnatamiz
COPY requirements.txt .
RUN pip install "setuptools<70" wheel \
    && pip install --no-build-isolation pyaes \
    && pip install -r requirements.txt

COPY . .

# Render PORT ni o'zi beradi (config.py shuni o'qiydi); 8080 — sukut
EXPOSE 8080
CMD ["python", "bot.py"]
