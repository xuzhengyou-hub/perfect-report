from report_backend.workflows.report_workflow import (
    build_image_appendix,
    render_synthesized_knowledge_markdown,
)


def test_render_synthesized_knowledge_markdown_appends_images() -> None:
    markdown = render_synthesized_knowledge_markdown(
        title="Experiment",
        synthesized="Structured summary",
        image_refs=["data/workspaces/demo/images/diagram.png"],
    )

    assert markdown.startswith("# Synthesized Knowledge: Experiment")
    assert "Structured summary" in markdown
    assert "## Reference Images" in markdown
    assert "![diagram](data/workspaces/demo/images/diagram.png)" in markdown

def test_build_image_appendix_returns_empty_for_no_images() -> None:
    assert build_image_appendix("Unused", []) == ""
