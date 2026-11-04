# Manim's official image already has Cairo, Pango, ffmpeg and a LaTeX install.
FROM manimcommunity/manim:v0.19.0

USER root
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY main.py /app/main.py
RUN mkdir -p /tmp/lerno-media && chown -R 1000:1000 /app /tmp/lerno-media

USER 1000
WORKDIR /app
ENV PORT=7860 MEDIA_DIR=/tmp/lerno-media
EXPOSE 7860
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
