# AutoQA 🚀

**AI-powered automated test generation, validation, and repair.**

AutoQA is a CLI and workflow engine to automatically create, validate, and execute tests for your codebase—unit, e2e, and manual QA checklists.

---

## ✨ Features

✅ Generate unit tests in **pytest** or **jest**  
✅ Generate e2e tests in **Cypress** or **Playwright**  
✅ Generate manual QA checklists  
✅ Repair failing tests automatically  
✅ Slack notifications for approvals and results  
✅ Supports monorepos, nested directories, glob filters  
✅ Config file support (`.autoqa.toml`)

---

## 🚀 Quickstart

**Install:**
```bash
pip install autoqa
````

**Generate tests:**

```bash
auto generate \
  --project ./my-app \
  --output-project ./qa-tests \
  --type unit \
  --framework pytest
```

**Resume workflows awaiting approval:**

```bash
auto resume --state pending_state_myfile.json
```

**Repaire a test file:**

```bash
auto repair-test \
  --source-file ./src/button.js \
  --test-file ./tests/button.test.js \
  --project-root ./ \
  --framework jest
```

---

## ⚙️ Example Config File

`.autoqa.toml`:

```toml
framework = "pytest"
output_project = "./qa-tests"
test_type = "unit"
exclude_dirs = ["node_modules", "dist"]
file_glob = "*.py"
```

---

## 📘 CLI Reference

### `generate`

Generate tests automatically for an entire project directory.

**Example:**

```bash
auto generate --project ./my-app --type unit --framework pytest
```

---

### `fix`

Automatically repair all tests in a project directory:

```bash
auto fix --project ./my-app --type unit --framework jest
```

---

### `repair-test`

Repair a **single test file** iteratively:

```bash
auto repair-test \
  --source-file ./src/my-module.js \
  --test-file ./tests/my-module.test.js \
  --project-root ./ \
  --framework jest
```

This command:

* Loads the source code and test file.
* Runs iterative repair cycles until the test passes or max retries are reached.
* Overwrites the test file with repaired content.
* Supports `pytest` and `jest`.

---

## 🙌 Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 📝 License

MIT © 2025 Shelton Wilson

---

## 📜 License

MIT © 2025 Shelton Wilson
