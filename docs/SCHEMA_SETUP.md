# YAML Schema Validation Setup

This project includes a comprehensive JSON Schema (`schemas/v1.json`) that enables IDE validation and autocomplete for your `dbt-config.yml` files.

## Benefits

✅ **Real-time validation** - Errors highlighted as you type  
✅ **Autocomplete** - Suggestions for valid properties  
✅ **Documentation** - Hover tooltips showing field descriptions  
✅ **Catch mistakes early** - Invalid YAML detected before running Terraform  

## Setup by IDE

### VS Code

**Option 1: Automatic (Recommended)**

1. Install the [YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) by Red Hat

2. Create `.vscode/settings.json` in your workspace:

```json
{
  "yaml.schemas": {
    "schemas/v1.json": "dbt-config.yml"
  }
}
```

3. Restart VS Code and open your `dbt-config.yml` - validation will be active immediately

**Option 2: Using $schema Directive**

Add this to the top of your `dbt-config.yml`:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/trouze/dbt-cloud-terraform-starter/refs/heads/main/schemas/v1.json
project:
  name: my_project
  # ... rest of config
```

**Option 3: Manual URI Mapping**

1. Install YAML extension
2. Open Settings → Extensions → YAML
3. Scroll to "Schemas" section
4. Add mapping:
   - **Glob Pattern**: `**/dbt-config.yml`
   - **Schema URL**: `./schemas/v1.json` (relative to workspace root)

### JetBrains IDEs (IntelliJ, PyCharm, WebStorm, etc.)

**Automatic Setup**

1. Open your project in the IDE
2. Create `dbt-config.yml` or edit existing one
3. Right-click in editor → Select "JSON Schema" → Configure Schema → New Schema
4. Set schema URL: `https://raw.githubusercontent.com/trouze/dbt-cloud-terraform-starter/refs/heads/main/schemas/v1.json`
5. Apply to file pattern: `dbt-config.yml`

**Or via settings.json**

Create `.idea/dictionaries/project.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="JsonSchemaMappingsProjectConfiguration">
    <state>
      <map>
        <entry key="dbt-config">
          <value>
            <SchemaInfo>
              <option name="name" value="dbt-config" />
              <option name="relativePathToSchema" value="schemas/v1.json" />
              <option name="schemaVersion" value="JSON schema version 7" />
              <option name="patterns">
                <list>
                  <Item>
                    <Item>
                      <name value="Path" />
                      <string>dbt-config.yml</string>
                    </Item>
                    <Item>
                      <name value="Path" />
                      <string>dbt-config.yaml</string>
                    </Item>
                  </Item>
                </list>
              </option>
            </SchemaInfo>
          </value>
        </entry>
      </map>
    </state>
  </component>
</JsonSchemaMappingsProjectConfiguration>
```

### Vim/Neovim

**Using vim-lsp with SchemaStore**

```vim
" ~/.config/nvim/init.vim or init.lua
let g:lsp_settings = {
  \ 'yaml-language-server': {
  \   'workspace_config': {
  \     'yaml': {
  \       'schemas': {
  \         'schemas/v1.json': '*.yml'
  \       }
  \     }
  \   }
  \ }
\}
```

### Sublime Text

Use the [YAML Language Server](https://packagecontrol.io/packages/YAML%20LS) package with configuration:

```json
{
  "yaml_lsp_config": {
    "yaml": {
      "schemas": {
        "schemas/v1.json": "dbt-config.yml"
      }
    }
  }
}
```

## Validating Without IDE

### Command Line Validation

Use `ajv` (Any JSON Validator):

```bash
# Install ajv CLI
npm install -g ajv-cli

# Validate your YAML against the schema
# (requires converting YAML to JSON first)
pip install pyyaml
python3 -c "
import yaml, json
with open('dbt-config.yml') as f:
    data = yaml.safe_load(f)
print(json.dumps(data))
" | ajv validate -s schemas/v1.json
```

Or using Python:

```bash
pip install jsonschema pyyaml

python3 -c "
import yaml, json
from jsonschema import validate, ValidationError

with open('dbt-config.yml') as f:
    config = yaml.safe_load(f)

with open('schemas/v1.json') as f:
    schema = json.load(f)

try:
    validate(instance=config, schema=schema)
    print('✅ Valid!')
except ValidationError as e:
    print(f'❌ Invalid: {e.message}')
    print(f'Path: {list(e.path)}')
"
```

### Pre-Commit Hook

Add schema validation to your pre-commit hooks by updating `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/adrienverge/yamllint
  rev: v1.35.1
  hooks:
    - id: yamllint
      args: ['--config-data', '{extends: default, rules: {line-length: {max: 120}}}']
      files: 'dbt-config\.yml$'

# Add custom schema validation
- repo: local
  hooks:
    - id: schema-validate
      name: Validate YAML against schema
      entry: python3 -c "import yaml, json; cfg=yaml.safe_load(open('dbt-config.yml')); schema=json.load(open('schemas/v1.json')); from jsonschema import validate; validate(instance=cfg, schema=schema)"
      language: system
      files: 'dbt-config\.yml$'
      stages: [commit]
```

## Schema Features

### What Gets Validated

✅ **Required fields** - Missing `name`, `type`, `connection_id`, etc.  
✅ **Type checking** - Strings, integers, booleans  
✅ **Enum values** - Only valid options like `type: [development|deployment]`  
✅ **Patterns** - Project names (alphanumeric, `_`, `-`), environment variable names  
✅ **Ranges** - Connection IDs > 0, num_threads 1-16, timeout_seconds 300-86400  
✅ **Array items** - Each schedule hour must be 0-23  
✅ **URL patterns** - GitHub/GitLab repository URL formats  
✅ **Required trigger fields** - All four trigger types must be specified  

### What Won't Be Validated

❌ Token validity (only schema knows structure)  
❌ Connection ID existence (requires dbt Cloud API check)  
❌ Git repository accessibility  
❌ Schema name existence in warehouse  

These are validated at `terraform apply` time.

## Common Schema Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `'project' is a required property` | Missing root `project:` key | Add `project:` at start of YAML |
| `'name' is a required property` | Missing project name | Add `name: my_project` |
| `'development' is not one of ['development', 'deployment']` | Invalid type value | Use `type: development` or `type: deployment` |
| `Additional properties are not allowed` | Extra fields in schema | Remove unknown keys like `timezone:` |
| `Expected integer, got string` | Wrong data type | Use `connection_id: 12345` not `"12345"` |
| `'dev_token' does not match '^[A-Z_]' | Env var name invalid format | Use UPPER_SNAKE_CASE for env vars |

## Troubleshooting IDE Validation

**VS Code shows no validation**

- [ ] YAML extension installed? Install from Extensions marketplace
- [ ] `.vscode/settings.json` created correctly? Check path format
- [ ] File named exactly `dbt-config.yml`? Schema only applies to exact name
- [ ] Restart VS Code? `⌘Q` then reopen
- [ ] Check extension output: View → Output → YAML Language Server

**JetBrains IDE shows no validation**

- [ ] Schema file path correct relative to project root?
- [ ] Try invalidating caches: File → Invalidate Caches / Restart
- [ ] Check XML syntax in `.idea/dictionaries/project.xml`
- [ ] Ensure `dbt-config.yml` is in project root, not subdirectory

**Schema validation too strict**

- Update to latest version of schema: Check GitHub for latest `v1.json`
- Report issues: [Open an issue](https://github.com/trouze/dbt-cloud-terraform-starter/issues)

## Using Remote Schema

The schema is hosted on GitHub and can be referenced directly:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/trouze/dbt-cloud-terraform-starter/refs/heads/main/schemas/v1.json
project:
  name: my_project
```

Benefits:
- Always uses latest schema
- No need to download file
- Automatic updates as project evolves

Drawbacks:
- Requires internet connection
- Slightly slower validation
- Uses GitHub as source of truth

## Next Steps

1. **Set up validation** - Choose IDE setup option from above
2. **Validate your config** - Open `dbt-config.yml` and check for red squiggles
3. **Test IDE features** - Type `project:` and see autocomplete
4. **Hover for docs** - Hover over field names to see descriptions
5. **Commit with confidence** - Schema catches errors before `terraform plan`

## Questions?

- See [Troubleshooting section in README](README.md#troubleshooting)
- Check [YAML Best Practices](README.md#yaml-best-practices)
- Review [YAML Validation Examples](README.md#yaml-validation-examples)
- Open an [issue on GitHub](https://github.com/trouze/dbt-cloud-terraform-starter/issues)
