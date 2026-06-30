"""
FORGE HARDENING FRAMEWORK — Mathematical Code Quality Assessment

OKF reference: ADVERSARIAL_PLAYBOOK_FOR_AI_CODEBASE_DOCS.md S3, S5, S6
"""
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HardeningScore:
    """Quantitative score for a code module."""
    module: str
    self_contained: float  # 0-1: can it break if deps change?
    breakability: float    # 0-1: how many ways can it fail?
    explainability: float  # 0-1: can a human understand it in <30s?
    attack_surface: float  # 0-1: how many input vectors for exploits?
    overall: float         # geometric mean of above

    def __repr__(self):
        return (
            f"  {self.module}:\n"
            f"    self_contained={self.self_contained:.2f}\n"
            f"    breakability={self.breakability:.2f}\n"
            f"    explainability={self.explainability:.2f}\n"
            f"    attack_surface={self.attack_surface:.2f}\n"
            f"    OVERALL={self.overall:.2f}"
        )


def measure_self_contained(filepath: Path) -> float:
    """Score 0-1: higher = more self-contained (fewer external deps)."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (SyntaxError, FileNotFoundError):
        return 0.0

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])

    # Stdlib modules are "free" — they're always available
    stdlib = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()
    external = [i for i in set(imports) if i not in stdlib and i != "forge_sdk"]

    if not external:
        return 1.0
    # Penalty: -0.15 per external dep (capped at 0)
    return max(0.0, 1.0 - len(external) * 0.15)


def measure_breakability(filepath: Path) -> float:
    """Score 0-1: higher = harder to break (fewer failure modes)."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (SyntaxError, FileNotFoundError):
        return 0.0

    risk = 0.0

    # Count bare except clauses (swallowing errors)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            risk += 0.1

    # Count eval/exec calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                risk += 0.3

    # Count shell=True usage
    if "shell=True" in source:
        risk += 0.2

    # Count unbounded loops (while True without break)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                has_break = any(isinstance(n, ast.Break) for n in ast.walk(node))
                if not has_break:
                    risk += 0.3

    # Count global state mutations
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            risk += 0.1

    return max(0.0, 1.0 - risk)


def measure_explainability(filepath: Path) -> float:
    """Score 0-1: higher = more explainable (comments, docstrings, naming)."""
    try:
        source = filepath.read_text()
        lines = source.split("\n")
    except FileNotFoundError:
        return 0.0

    if not lines:
        return 0.0

    # Docstring coverage
    try:
        tree = ast.parse(source)
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        documented = sum(1 for f in functions if ast.get_docstring(f))
        documented += sum(1 for c in classes if ast.get_docstring(c))
        total = len(functions) + len(classes)
        doc_ratio = documented / max(total, 1)
    except SyntaxError:
        doc_ratio = 0.0

    # Comment density (lines with # that aren't shebang/encoding)
    comment_lines = sum(1 for l in lines if l.strip().startswith("#") and not l.strip().startswith("#!"))
    comment_density = min(comment_lines / max(len(lines), 1), 0.3)  # Cap at 30%

    # Average line length (shorter = more readable)
    avg_len = sum(len(l) for l in lines) / max(len(lines), 1)
    length_score = max(0.0, 1.0 - (avg_len - 60) / 100)  # Penalty after 60 chars

    return (doc_ratio * 0.5 + comment_density * 0.2 + length_score * 0.3)


def measure_attack_surface(filepath: Path) -> float:
    """Score 0-1: higher = smaller attack surface (fewer input vectors)."""
    try:
        source = filepath.read_text()
    except FileNotFoundError:
        return 0.0

    risk = 0.0

    # String formatting in SQL/commands (injection vectors)
    if re.search(r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE|EXEC)', source, re.IGNORECASE):
        risk += 0.3
    if re.search(r'\.format\(.*(?:SELECT|INSERT|UPDATE|DELETE)', source, re.IGNORECASE):
        risk += 0.3

    # pickle/yaml.load (deserialization attacks)
    if "pickle.load" in source or "pickle.loads" in source:
        risk += 0.3
    if "yaml.load(" in source and "Loader=" not in source:
        risk += 0.2

    # subprocess with shell=True
    if "subprocess.run" in source and "shell=True" in source:
        risk += 0.3

    # eval/exec
    if re.search(r'\beval\b|\bexec\b', source):
        risk += 0.3

    # open() without explicit encoding
    if re.search(r'open\([^)]+\)(?!\.read|\.write)', source):
        risk += 0.05

    # getattr with user input
    if "getattr(" in source:
        risk += 0.1

    return max(0.0, 1.0 - risk)


def harden_file(filepath: Path) -> HardeningScore:
    """Compute full hardening score for a file."""
    sc = measure_self_contained(filepath)
    br = measure_breakability(filepath)
    ex = measure_explainability(filepath)
    at = measure_attack_surface(filepath)
    overall = (sc * br * ex * at) ** 0.25  # Geometric mean
    return HardeningScore(
        module=filepath.name,
        self_contained=sc,
        breakability=br,
        explainability=ex,
        attack_surface=at,
        overall=overall,
    )


def harden_directory(dirpath: Path, pattern: str = "**/*.py") -> list[HardeningScore]:
    """Score all Python files in a directory."""
    scores = []
    for f in sorted(dirpath.glob(pattern)):
        if f.name == "__init__.py" or "test_" in f.name or "__pycache__" in str(f):
            continue
        scores.append(harden_file(f))
    return scores


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/srinji/forge/src/forge_sdk")

    if target.is_file():
        scores = [harden_file(target)]
    else:
        scores = harden_directory(target)

    print("=" * 60)
    print("FORGE HARDENING SCORECARD")
    print("=" * 60)

    for s in sorted(scores, key=lambda x: x.overall):
        print(s)

    if scores:
        avg = sum(s.overall for s in scores) / len(scores)
        worst = min(scores, key=lambda x: x.overall)
        print(f"\n  AVERAGE: {avg:.2f}")
        print(f"  WORST:   {worst.module} ({worst.overall:.2f})")
        print(f"  FILES:   {len(scores)}")
