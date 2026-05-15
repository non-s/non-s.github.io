"""Tests for utils/frontmatter.py"""
import pytest
from utils.frontmatter import parse, get_str, get_list


SIMPLE_POST = """---
title: "Hello World"
date: 2026-01-15
categories: [world, politics]
tags: [breaking, news]
featured: false
---

Body content here.
"""

BLOCK_LIST_POST = """---
title: Block Tags
tags:
  - artificial-intelligence
  - machine-learning
  - deep-learning
---
"""

UNQUOTED_POST = """---
title: Unquoted Title Here
description: A simple description without quotes
---
"""


def test_parse_simple():
    fm = parse(SIMPLE_POST)
    assert fm["title"] == "Hello World"
    assert fm["date"] == "2026-01-15"
    assert fm["featured"] == "false"


def test_parse_inline_array():
    fm = parse(SIMPLE_POST)
    assert fm["categories"] == ["world", "politics"]
    assert fm["tags"] == ["breaking", "news"]


def test_parse_block_list():
    fm = parse(BLOCK_LIST_POST)
    assert "artificial-intelligence" in fm["tags"]
    assert "machine-learning" in fm["tags"]
    assert len(fm["tags"]) == 3


def test_parse_unquoted():
    fm = parse(UNQUOTED_POST)
    assert fm["title"] == "Unquoted Title Here"
    assert "simple description" in fm["description"]


def test_parse_no_frontmatter():
    assert parse("No frontmatter here") == {}


def test_parse_empty_frontmatter():
    assert parse("---\n---\n\nbody") == {}


def test_get_str_scalar():
    fm = parse(SIMPLE_POST)
    assert get_str(fm, "title") == "Hello World"


def test_get_str_from_list():
    fm = parse(SIMPLE_POST)
    assert get_str(fm, "categories") == "world"


def test_get_str_missing():
    assert get_str({}, "missing", "default") == "default"


def test_get_list_scalar():
    fm = {"tags": "single"}
    assert get_list(fm, "tags") == ["single"]


def test_get_list_list():
    fm = parse(SIMPLE_POST)
    assert get_list(fm, "tags") == ["breaking", "news"]


def test_get_list_missing():
    assert get_list({}, "tags") == []
