# Contributing to dbt Cloud Terraform Modules

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

Please be respectful and constructive in all interactions.

## How to Contribute

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
   git clone https://github.com/your-username/dbt-terraform-modules-yaml.git
   cd dbt-terraform-modules-yaml
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the existing code style
   - Add comments for complex logic
   - Update documentation as needed

3. **Test your changes**
   ```bash
   terraform init
   terraform validate
   terraform plan
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

- Terraform >= 1.0
- Git
- A dbt Cloud account for testing

### Local Development

```bash
git clone https://github.com/your-username/dbt-terraform-modules-yaml.git
cd dbt-terraform-modules-yaml

# Set up your test environment
cp examples/basic/terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your credentials

terraform init
terraform plan
```

## Testing

Before submitting a PR:

```bash
# Validate syntax
terraform validate

# Format check
terraform fmt -check -recursive

# Plan to check for errors
terraform plan
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

- Check existing [GitHub issues](https://github.com/yourusername/dbt-terraform-modules-yaml/issues)
- Review the [README](../README.md) and [documentation](../README.md#documentation)
- Open a new discussion in GitHub Discussions

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.

Thank you for contributing! 🎉
