import pytest

from src.core.utils import clean_article_title, extract_source_from_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.example.com/article", "Example"),
        ("https://alice.substack.com/p/post", "Alice (Substack)"),
        ("https://openai.com/blog", "OpenAI"),
        ("https://blog.example.co.uk/story", "Blog"),
        ("", ""),
    ],
)
def test_extract_source_from_url(url, expected):
    assert extract_source_from_url(url) == expected


def test_clean_article_title_removes_noise():
    title = "[Firehose] Fwd:  Hello World"
    assert clean_article_title(title) == "Hello World"


@pytest.mark.parametrize(
    "title,expected",
    [("", "Untitled Article"), ("untitled", "Article Commentary"),],
)
def test_clean_article_title_edge_cases(title, expected):
    assert clean_article_title(title) == expected
