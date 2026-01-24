# Documentation Templates

> Reusable templates for creating consistent architecture documentation

## Overview

This directory contains templates for creating new architecture documentation. Using these templates ensures consistency across all documentation and makes it easier for readers to find information.

## Available Templates

| Template                                       | Purpose           | Use When                                            |
| ---------------------------------------------- | ----------------- | --------------------------------------------------- |
| [hub-template.md](./hub-template.md)           | Hub index page    | Creating a new documentation hub                    |
| [document-template.md](./document-template.md) | Standard document | Documenting a component, service, or feature        |
| [dataflow-template.md](./dataflow-template.md) | End-to-end trace  | Documenting a complete data flow through the system |

## How to Use

### Creating a New Hub

1. Copy `hub-template.md` to `docs/architecture/{hub-name}/README.md`
2. Replace all `{placeholder}` values
3. Add the hub to the main index at `docs/architecture/README.md`

```bash
cp docs/architecture/templates/hub-template.md docs/architecture/new-hub/README.md
```

### Creating a New Document

1. Copy `document-template.md` to the appropriate hub directory
2. Replace all `{placeholder}` values
3. Add the document to the hub's README

```bash
cp docs/architecture/templates/document-template.md docs/architecture/some-hub/new-document.md
```

### Creating a Dataflow Document

1. Copy `dataflow-template.md` to `docs/architecture/dataflows/`
2. Replace all `{placeholder}` values
3. Add the dataflow to the dataflows hub README

```bash
cp docs/architecture/templates/dataflow-template.md docs/architecture/dataflows/new-flow.md
```

## Template Conventions

### Placeholders

All placeholders use curly braces: `{Placeholder Name}`

Replace these with actual content before committing.

### Code Citations

Templates include examples of proper code citation format:

- Single line: `path/to/file.py:67`
- Range: `path/to/file.py:67-89`

### Diagrams

Templates include Mermaid diagram examples. Customize these for your specific documentation needs.

## Validation

After creating documentation from templates, validate your work:

```bash
python -m scripts.validate_docs docs/architecture/
```

## Related

- [STANDARDS.md](../STANDARDS.md) - Documentation standards and formatting rules
- [README.md](../README.md) - Main architecture documentation index
