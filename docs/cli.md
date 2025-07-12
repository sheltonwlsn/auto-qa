# CLI Commands

## Generate tests

```bash
auto generate --project ./my-app --type unit --framework pytest
```

## Repair a test

```bash
auto repair-test --source-file ./src/module.js --test-file ./tests/module.test.js --project-root ./ --framework jest
```

## Fix all tests in a project

```bash
auto fix --project ./my-app --type unit --framework jest
```
