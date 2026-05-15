from apps.src.issue_docent.llm.prompt_loader import load_prompt


def test_load_prompt_reads_prompt_file():
    prompt = load_prompt("article_brief.md")

    assert "Article Brief Prompt" in prompt


def test_load_prompt_reads_quiz_prompt_file():
    prompt = load_prompt("quiz.md")

    assert "Issue Docent Quiz Prompt" in prompt
