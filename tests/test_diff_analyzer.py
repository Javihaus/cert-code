"""
Tests for the diff analyzer.
"""

from cert_code.analyzers.diff import (
    detect_language,
    detect_primary_language,
    extract_added_content,
    parse_diff,
)
from cert_code.models import Language


class TestLanguageDetection:
    """Tests for language detection."""

    def test_detect_python(self):
        assert detect_language("src/main.py") == Language.PYTHON
        assert detect_language("utils.pyi") == Language.PYTHON

    def test_detect_javascript(self):
        assert detect_language("app.js") == Language.JAVASCRIPT
        assert detect_language("component.jsx") == Language.JAVASCRIPT
        assert detect_language("module.mjs") == Language.JAVASCRIPT

    def test_detect_typescript(self):
        assert detect_language("app.ts") == Language.TYPESCRIPT
        assert detect_language("component.tsx") == Language.TYPESCRIPT

    def test_detect_go(self):
        assert detect_language("main.go") == Language.GO

    def test_detect_rust(self):
        assert detect_language("lib.rs") == Language.RUST

    def test_detect_other(self):
        assert detect_language("Makefile") == Language.OTHER
        assert detect_language("README") == Language.OTHER
        assert detect_language("file.unknown") == Language.OTHER


class TestPrimaryLanguageDetection:
    """Tests for primary language detection from multiple files."""

    def test_single_language(self):
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        assert detect_primary_language(files) == Language.PYTHON

    def test_mixed_languages_python_dominant(self):
        files = [
            "src/main.py",
            "src/utils.py",
            "config.json",
            "README.md",
        ]
        assert detect_primary_language(files) == Language.PYTHON

    def test_mixed_languages_typescript_dominant(self):
        files = [
            "src/App.tsx",
            "src/components/Button.tsx",
            "package.json",
            "tsconfig.json",
        ]
        assert detect_primary_language(files) == Language.TYPESCRIPT

    def test_empty_list(self):
        assert detect_primary_language([]) == Language.OTHER

    def test_only_other_files(self):
        files = ["README.md", "Makefile", ".gitignore"]
        assert detect_primary_language(files) == Language.OTHER


class TestDiffParsing:
    """Tests for diff parsing."""

    def test_parse_simple_diff(self):
        diff = """diff --git a/src/utils.py b/src/utils.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/utils.py
@@ -0,0 +1,5 @@
+def hello():
+    print("Hello")
+
+def world():
+    print("World")
"""
        artifact = parse_diff(diff)

        assert artifact.language == Language.PYTHON
        assert "src/utils.py" in artifact.files_changed
        assert artifact.diff_stats.additions == 5
        assert artifact.diff_stats.deletions == 0
        assert artifact.diff_stats.files_changed == 1

    def test_parse_modification_diff(self):
        diff = """diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,5 @@
-def old_function():
-    pass
+def new_function():
+    print("New implementation")
+    return True
"""
        artifact = parse_diff(diff)

        assert artifact.language == Language.PYTHON
        assert artifact.diff_stats.additions == 3
        assert artifact.diff_stats.deletions == 2

    def test_parse_multiple_files(self):
        diff = """diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,1 +1,2 @@
 existing line
+new line

diff --git a/src/utils.py b/src/utils.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/utils.py
@@ -0,0 +1,3 @@
+def helper():
+    pass
+
"""
        artifact = parse_diff(diff)

        assert len(artifact.files_changed) == 2
        assert "src/main.py" in artifact.files_changed
        assert "src/utils.py" in artifact.files_changed
        assert artifact.diff_stats.files_changed == 2

    def test_parse_with_language_override(self):
        diff = """diff --git a/script b/script
new file mode 100644
--- /dev/null
+++ b/script
@@ -0,0 +1,1 @@
+#!/bin/bash
"""
        # Without override, would be OTHER
        artifact = parse_diff(diff)
        assert artifact.language == Language.OTHER

        # With override
        artifact = parse_diff(diff, language=Language.SHELL)
        assert artifact.language == Language.SHELL


class TestExtractAddedContent:
    """Tests for extracting added content."""

    def test_extract_added_lines(self):
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,2 +1,4 @@
 existing line
+new line 1
+new line 2
 another existing line
"""
        added = extract_added_content(diff)

        assert "new line 1" in added
        assert "new line 2" in added
        assert "existing line" not in added

    def test_extract_no_additions(self):
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,2 @@
 line 1
-removed line
 line 2
"""
        added = extract_added_content(diff)
        assert added == ""

    def test_exclude_diff_headers(self):
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -0,0 +1,1 @@
+actual content
"""
        added = extract_added_content(diff)

        # Should not include the +++ header
        assert "+++ b/test.py" not in added
        assert "actual content" in added
