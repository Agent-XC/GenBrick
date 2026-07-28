"""Gradio wrapper deploying predict() as a public HF Space (issue #21).

Sync (see .github/workflows/deploy-space.yml) flattens this directory's
contents into the HF Space git repo's root, so predict.py sits next to this
file with no `space` package wrapping it there — the import falls back
accordingly.
"""

try:
    from space.predict import predict
except ImportError:
    from predict import predict

import gradio as gr

demo = gr.Interface(
    fn=predict,
    inputs=gr.Textbox(label="Caption", placeholder="a small red car"),
    outputs=gr.JSON(label="Generated design"),
    title="GenBrick — BrickNet caption-to-design generation",
    description=(
        "Fan project, not affiliated with or endorsed by the LEGO Group. "
        "Type a caption and generate a novel LEGO design as LDR text."
    ),
)

if __name__ == "__main__":
    # No CORS override needed: Gradio's CustomCORSMiddleware only restricts
    # cross-origin requests when the Space's own Host header resolves to
    # localhost/127.0.0.1/0.0.0.0 (a local-dev CSRF guard) — see
    # gradio/route_utils.py's is_valid_origin. A real deployed Space's host is
    # never one of those, so it already answers a github.io frontend's
    # cross-origin fetch() with Access-Control-Allow-Origin by default.
    demo.launch()
