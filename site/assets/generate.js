// Wired to the live Space deployed in issue #21 (space/app.py's `_generate`,
// wrapping space/predict.py's predict()). No server of our own here — this
// page talks straight to Gradio's public "call" HTTP API:
//   1. POST /gradio_api/call/<api_name>  {data: [caption]} -> {event_id}
//   2. GET  /gradio_api/call/<api_name>/<event_id>          -> SSE stream,
//      whose final "complete"/"error" event carries the result.
// See gradio/routes.py's simple_predict_post/simple_predict_get for the
// exact contract this mirrors.
const SPACE_URL = "https://xcoubez-genbrick.hf.space";
const API_NAME = "_generate";

// ZeroGPU cold starts (Space asleep) plus one generation can take a while;
// this is a client-side ceiling so a hung request doesn't spin forever, not
// a retry mechanism — issue #22 explicitly wants no retry loop.
const TIMEOUT_MS = 120000;

// Parses one Gradio "call" API SSE response body. Only the last
// "complete"/"error" event matters — "generating"/"heartbeat" events along
// the way are progress-only and carry no final result.
function parseCallStream(streamText) {
  let event = null;
  let data = null;

  for (const block of streamText.split("\n\n")) {
    const eventMatch = block.match(/^event: (.+)$/m);
    const dataMatch = block.match(/^data: (.*)$/m);
    if (!eventMatch || !dataMatch) continue;
    if (eventMatch[1] === "complete" || eventMatch[1] === "error") {
      event = eventMatch[1];
      data = JSON.parse(dataMatch[1]);
    }
  }

  if (event === "complete") {
    return data[0].ldr;
  }
  // gr.Error surfaces here as {error: "<message>", ...} (see
  // gradio/routes.py's simple_predict_get) — space/app.py's _generate
  // re-raises predict()'s real exception message this way (issue #21).
  const message = typeof data === "string" ? data : data && data.error ? data.error : "Generation failed.";
  throw new Error(message);
}

async function generateDesign(caption, signal) {
  const postResponse = await fetch(`${SPACE_URL}/gradio_api/call/${API_NAME}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: [caption] }),
    signal,
  });
  if (!postResponse.ok) {
    throw new Error(`Space request failed (${postResponse.status}).`);
  }
  const { event_id } = await postResponse.json();

  const getResponse = await fetch(`${SPACE_URL}/gradio_api/call/${API_NAME}/${event_id}`, {
    signal,
  });
  if (!getResponse.ok) {
    throw new Error(`Space response failed (${getResponse.status}).`);
  }
  return parseCallStream(await getResponse.text());
}

function setStatus(message, className) {
  const status = document.getElementById("generate-status");
  status.textContent = message;
  status.className = className;
}

document.getElementById("generate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const caption = document.getElementById("caption-input").value.trim();
  if (!caption) {
    return;
  }

  const button = document.getElementById("generate-button");
  const result = document.getElementById("generate-result");
  result.textContent = "";
  button.disabled = true;
  setStatus("Generating… this can take a couple of minutes on a cold Space.", "status-loading");

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const ldr = await generateDesign(caption, controller.signal);
    setStatus("", "");
    result.textContent = ldr;
  } catch (error) {
    const message =
      error.name === "AbortError" ? "Timed out waiting for the Space to respond." : error.message;
    setStatus(message, "status-error");
    console.error(error);
  } finally {
    clearTimeout(timeoutId);
    button.disabled = false;
  }
});
