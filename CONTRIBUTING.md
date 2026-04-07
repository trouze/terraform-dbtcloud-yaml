# Contributing to terraform-dbtcloud-as-yaml

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

All contributors must follow the [dbt Community Code of Conduct](https://docs.getdbt.com/community/resources/code-of-conduct). See also [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) in this repository.

## How to Contribute

### Reporting security issues

Do not open a public issue. Follow [SECURITY.md](SECURITY.md).

### Reporting Bugs

If you find a bug, please create an issue with:

- Clear description of the bug
- Steps to reproduce
- Expected vs. actual behavior
- Your environment (Terraform version, OS, etc.)
- Any relevant configuration snippets

### Suggesting Features

Feature requests are welcome! Please include:

- Description of the feature
- Use case and why it's needed
- Any examples or mockups

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/your-username/terraform-dbtcloud-as-yaml.git
   cd terraform-dbtcloud-as-yaml
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the existing code style
   - Add comments for complex logic
   - Update documentation as needed

3. **Test your changes**
   ```bash
   make fmt      # auto-format
   make test     # run tests with mock providers (no credentials needed)
   make lint     # run tflint
   ```

4. **Commit with clear messages**
   ```bash
   git commit -m "Add: clear description of changes"
   ```

5. **Push and open a PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## Development Setup

### Prerequisites

- Terraform >= 1.7 (use [tfenv](https://github.com/tfutils/tfenv) or [asdf](https://asdf-vm.com/) — `.terraform-version` is provided)
- [tflint](https://github.com/terraform-linters/tflint)
- Git

### Local Development

```bash
git clone https://github.com/your-username/terraform-dbtcloud-as-yaml.git
cd terraform-dbtcloud-as-yaml

terraform init -backend=false
```

### Available Make Targets

Run `make help` to see all targets:

```
make fmt           # Auto-format all Terraform files
make fmt-check     # Check formatting without modifying (used in CI)
make lint          # Run tflint on all modules
make validate      # Run terraform validate
make test          # Run terraform test with mock providers (no credentials needed)
make docs          # Regenerate terraform-docs for all modules
make pre-commit    # Run all pre-commit hooks on staged files
```

## Testing

Before submitting a PR:

```bash
make fmt-check   # verify formatting
make test        # runs all tests against mock providers — no dbt Cloud credentials needed
make lint        # check for linting issues
```

## Documentation

- Update `README.md` for user-facing changes
- Update module `variables.tf` with clear descriptions
- Add comments to complex logic
- Include examples for new features

## Release Process

Maintainers will:

1. Update version numbers following [Semantic Versioning](https://semver.org/)
2. Update `CHANGELOG.md`
3. Create a GitHub release with release notes
4. Tag the commit with version number

## Questions?

- Check existing [GitHub issues](https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/issues)
- Review the [README](../README.md) and [documentation](../README.md#documentation)
- Open a new discussion in GitHub Discussions

## License

By contributing, you agree that your contributions will be licensed under the project's [Apache License 2.0](LICENSE).

Thank you for contributing!
