# Refactoring Plan: Adopt Standard Src Layout 🏗️

## 🎯 Goal
Refactor the project structure to follow Python [packaging best practices](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).
Transition from "Root Package in `src`" to "**Src Layout**" where `src` is a container for the actual package `my_llm_sdk`.

**Current:** `from src.client import ...`
**Target:** `from my_llm_sdk.client import ...`

## ⚠️ Risks & Considerations
*   **Breaking Changes**: This changes all import paths. External scripts using `src` will break.
    *   **Decision**: **NO Compatibility Layer**. We will make a clean break. `import src` will fail.
*   **Git Diff**: Moving files will create a large diff history (files renamed).
*   **Verification**: Must ensure dependency installation (`pip install -e .`) works correctly after the move.

---

## 📋 Implementation Steps

### 1. File Structure Reorganization
*   [ ] Create new package directory: `src/my_llm_sdk`
*   [ ] Move existing python modules (`client.py`, `cli.py`, `__init__.py`) and packages (`providers`, `budget`, `config`, `doctor`, `utils`) into `src/my_llm_sdk`.
*   [ ] Verify `src/` only contains `my_llm_sdk/` directory.

### 2. Codebase Import Updates (Mass Replace)
*   [ ] **Import Style Decision**: Use **Absolute Imports** (e.g., `from my_llm_sdk.client import ...`) for consistency and clarity. Avoid mixed styles.
*   [ ] **Internal Source Code**:
    *   Replace `from src.` with `from my_llm_sdk.`
    *   Replace `import src.` with `import my_llm_sdk.`
*   [ ] **Configuration Files**:
    *   Update `pyproject.toml`: 
        *   Update entry point to `my_llm_sdk.cli:main`.
        *   Ensure build backend (Hatchling) finds the package. (Verify outcome: wheel contains `my_llm_sdk`).
*   [ ] **Verification Scripts & Tests**:
    *   Update `verify_*.py` files in root.
    *   Update `tests/*.py` files to import from `my_llm_sdk`.

### 3. Documentation Updates
*   [ ] Update `README_zh.md` and `README.md` code snippets to show `from my_llm_sdk.client import LLMClient`.

### 4. Verification (The "Golden Standard")
*   [ ] **Negative Test**: `python -c "import src"` must FAIL.
*   [ ] **Editable Install**: `pip install -e .` -> `python verify_all.py` passes.
*   [ ] **Wheel Build**: `python -m build`.
*   [ ] **Production Install Check**: 
    *   Create fresh venv.
    *   `pip install dist/*.whl`.
    *   `python -c "import my_llm_sdk; print(my_llm_sdk.__name__)"` should pass.

### 5. Release Discipline
*   [ ] **Bump Version**: Increment version in `pyproject.toml` (e.g., `0.3.5`).
*   [ ] **Release Notes**: Add entry to CHANGELOG/README detailing the breaking change + migration guide.

---

## 🔍 Detailed Change List

### Files to Move
```text
src/
├── budget/      -> src/my_llm_sdk/budget/
├── config/      -> src/my_llm_sdk/config/
├── doctor/      -> src/my_llm_sdk/doctor/
├── providers/   -> src/my_llm_sdk/providers/
├── utils/       -> src/my_llm_sdk/utils/
├── client.py    -> src/my_llm_sdk/client.py
├── cli.py       -> src/my_llm_sdk/cli.py
├── schemas.py   -> src/my_llm_sdk/schemas.py
└── __init__.py  -> src/my_llm_sdk/__init__.py
```

### Pyproject.toml Updates
```toml
[project.scripts]
llm-sdk = "my_llm_sdk.cli:main"  # Was src.cli:main

[tool.hatch.build.targets.wheel]
packages = ["src/my_llm_sdk"]    # Explicit path
```
