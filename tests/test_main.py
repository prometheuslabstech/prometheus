"""Tests for main module."""

import pytest
from prometheus.main import main


def test_main_default(capsys):
    """Test main function with default arguments."""
    main()
    captured = capsys.readouterr()
    assert "Hello, World!" in captured.out


def test_main_with_name(capsys):
    """Test main function with a custom name."""
    main("Alice")
    captured = capsys.readouterr()
    assert "Hello, Alice!" in captured.out

