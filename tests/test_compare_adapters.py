from space.compare_adapters import compare_adapter_stacks, render_report
from tests.test_predict import VALID_PATH_TEXT

INVALID_PATH_TEXT = "not valid path text"

FAKE_STACKS = {"none": (), "pt": ("pt-adapter",), "pt+sft": ("pt-adapter", "sft-adapter")}


def _recording_generate(calls, responses):
    def generate(caption, adapter_ids, seed):
        calls.append((caption, adapter_ids, seed))
        return responses[(caption, adapter_ids)]

    return generate


def test_compare_adapter_stacks_runs_every_caption_through_every_stack():
    calls = []
    responses = {
        ("a red car", ()): VALID_PATH_TEXT,
        ("a red car", ("pt-adapter",)): VALID_PATH_TEXT,
        ("a red car", ("pt-adapter", "sft-adapter")): VALID_PATH_TEXT,
    }

    results = compare_adapter_stacks(
        ["a red car"],
        seeds={"a red car": 7},
        adapter_stacks=FAKE_STACKS,
        generate=_recording_generate(calls, responses),
    )

    assert calls == [
        ("a red car", (), 7),
        ("a red car", ("pt-adapter",), 7),
        ("a red car", ("pt-adapter", "sft-adapter"), 7),
    ]
    assert [r.stack_name for r in results] == ["none", "pt", "pt+sft"]


def test_compare_adapter_stacks_holds_seed_constant_per_caption_across_stacks_only():
    calls = []
    responses = {
        ("a red car", ()): VALID_PATH_TEXT,
        ("a red car", ("pt-adapter",)): VALID_PATH_TEXT,
        ("a red car", ("pt-adapter", "sft-adapter")): VALID_PATH_TEXT,
        ("a red boat", ()): VALID_PATH_TEXT,
        ("a red boat", ("pt-adapter",)): VALID_PATH_TEXT,
        ("a red boat", ("pt-adapter", "sft-adapter")): VALID_PATH_TEXT,
    }

    compare_adapter_stacks(
        ["a red car", "a red boat"],
        seeds={"a red car": 1, "a red boat": 2},
        adapter_stacks=FAKE_STACKS,
        generate=_recording_generate(calls, responses),
    )

    seeds_used = {caption: {seed for c, _adapters, seed in calls if c == caption} for caption in ("a red car", "a red boat")}
    assert seeds_used == {"a red car": {1}, "a red boat": {2}}


def test_compare_adapter_stacks_records_parse_success_and_failure():
    calls = []
    responses = {
        ("a caption", ()): INVALID_PATH_TEXT,
        ("a caption", ("pt-adapter",)): VALID_PATH_TEXT,
    }
    stacks = {"none": (), "pt": ("pt-adapter",)}

    results = compare_adapter_stacks(
        ["a caption"],
        seeds={"a caption": 0},
        adapter_stacks=stacks,
        generate=_recording_generate(calls, responses),
    )

    none_result, pt_result = results
    assert none_result.parsed_ok is False
    assert "node line missing" in none_result.parse_error
    assert pt_result.parsed_ok is True
    assert pt_result.parse_error is None


def test_render_report_shows_caption_stack_parse_status_and_raw_text():
    calls = []
    responses = {
        ("a caption", ()): INVALID_PATH_TEXT,
        ("a caption", ("pt-adapter",)): VALID_PATH_TEXT,
    }
    stacks = {"none": (), "pt": ("pt-adapter",)}

    results = compare_adapter_stacks(
        ["a caption"],
        seeds={"a caption": 3},
        adapter_stacks=stacks,
        generate=_recording_generate(calls, responses),
    )
    report = render_report(results)

    assert "a caption" in report
    assert "seed=3" in report
    assert "none" in report
    assert "pt" in report
    assert INVALID_PATH_TEXT in report
    assert "<code>a brick 2x4 \\| red<br></code>" in report  # table-escaped `|`, newline as <br>
    assert "node line missing" in report


def test_render_report_escapes_html_metacharacters_in_generated_text():
    # Regression test: an earlier version wrapped path_text in a backtick
    # code span and converted "\n" to "<br>" — but a code span renders its
    # contents literally, so the "<br>" never became a line break, and any
    # backtick in the (arbitrary, LLM-generated) text would have prematurely
    # closed the span and corrupted the table row.
    weird_text = "a brick 2x4 ` red\nb plate 1x1 <tag> & more\n"
    calls = []
    stacks = {"none": ()}

    results = compare_adapter_stacks(
        ["a caption"],
        seeds={"a caption": 0},
        adapter_stacks=stacks,
        generate=_recording_generate(calls, {("a caption", ()): weird_text}),
    )
    report = render_report(results)

    assert "<code>a brick 2x4 ` red<br>b plate 1x1 &lt;tag&gt; &amp; more<br></code>" in report
