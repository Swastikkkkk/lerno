"""HF Space entry (Gradio SDK, ZeroGPU free tier). Copy ../main.py next to this file.
Gradio owns the server there, so Lerno's FastAPI routes are added to the app Gradio creates,
plus open CORS for the Vercel frontend."""
import os
os.environ.setdefault("GRADIO_SSR_MODE", "false")

import spaces
import gradio as gr
import gradio.routes as gr_routes
from fastapi.middleware.cors import CORSMiddleware
from main import app as lerno


@spaces.GPU(duration=1)
def _noop():
    return "ok"  # ZeroGPU needs one GPU function; Lerno itself runs on CPU


_create = gr_routes.App.create_app


def _create_with_lerno(*args, **kwargs):
    gapp = _create(*args, **kwargs)
    for route in reversed([r for r in lerno.routes if getattr(r, "path", "") not in ("/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect")]):
        gapp.router.routes.insert(0, route)
    gapp.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    return gapp


gr_routes.App.create_app = staticmethod(_create_with_lerno)

with gr.Blocks(title="Lerno backend") as demo:
    gr.Markdown("Lerno.ai backend is running. API: /health, /generate, /jobs/{id}, /chat")

if __name__ == "__main__":
    demo.launch(ssr_mode=False)
