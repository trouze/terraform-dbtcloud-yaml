# Interactive Mode Alternatives Comparison

This document shows code examples for different Python libraries that could be used to add interactive text-based menus to the importer CLI, similar to `dbtcloud-terraforming`'s interactive mode.

## Option 1: InquirerPy (Recommended)

**Pros**: Form-like interface similar to `huh`, rich features, good Rich integration  
**Cons**: Additional dependency, slightly more complex API

### Example Implementation

```python
# importer/interactive.py
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console

console = Console()

def prompt_fetch_interactive():
    """Interactive prompts for fetch command."""
    # Credentials (if not in env)
    account_id = inquirer.text(
        message="Account ID:",
        default=get_settings().account_id or "",
        validate=lambda result: result.isdigit() or "Account ID must be numeric"
    ).execute()
    
    token = inquirer.secret(
        message="API Token:",
        default=get_settings().api_token or "",
    ).execute()
    
    host = inquirer.text(
        message="Host URL:",
        default=get_settings().host or "https://cloud.getdbt.com",
    ).execute()
    
    # Fetch options
    output_path = inquirer.filepath(
        message="Output file path (optional):",
        default="dev_support/samples/account.json",
        only_files=False,
    ).execute()
    
    auto_timestamp = inquirer.confirm(
        message="Add timestamp to filename?",
        default=True,
    ).execute()
    
    compact = inquirer.confirm(
        message="Use compact JSON format?",
        default=False,
    ).execute()
    
    return {
        "account_id": account_id,
        "token": token,
        "host": host,
        "output": output_path if output_path else None,
        "auto_timestamp": auto_timestamp,
        "compact": compact,
    }
```

**Visual Output**:
```
┌─────────────────────────────────────┐
│ Account ID: [12345____________]   │
│                                     │
│ API Token:  [****************]     │
│                                     │
│ Host URL:   [https://cloud.getdbt.com]│
│                                     │
│ Output file: [dev_support/samples/account.json]│
│                                     │
│ Add timestamp? (Y/n): [Y]          │
│ Compact JSON? (y/N): [N]           │
└─────────────────────────────────────┘
```

---

## Option 2: Questionary (Simpler Alternative)

**Pros**: Simpler API, lightweight, good for basic prompts  
**Cons**: Less feature-rich, no built-in file browser, less form-like

### Example Implementation

```python
# importer/interactive.py
import questionary
from pathlib import Path

def prompt_fetch_interactive():
    """Interactive prompts for fetch command."""
    # Credentials
    account_id = questionary.text(
        "Account ID:",
        default=str(get_settings().account_id) if get_settings().account_id else "",
        validate=lambda text: text.isdigit() or "Must be numeric"
    ).ask()
    
    token = questionary.password("API Token:").ask()
    
    host = questionary.text(
        "Host URL:",
        default=get_settings().host or "https://cloud.getdbt.com"
    ).ask()
    
    # Options
    output_path = questionary.path(
        "Output file path (optional):",
        default="dev_support/samples/account.json",
        only_directories=False
    ).ask()
    
    auto_timestamp = questionary.confirm(
        "Add timestamp to filename?",
        default=True
    ).ask()
    
    compact = questionary.confirm(
        "Use compact JSON format?",
        default=False
    ).ask()
    
    return {
        "account_id": int(account_id),
        "token": token,
        "host": host,
        "output": Path(output_path) if output_path else None,
        "auto_timestamp": auto_timestamp,
        "compact": compact,
    }
```

**Visual Output**:
```
Account ID: 12345
API Token: ********
Host URL: https://cloud.getdbt.com
Output file path (optional): dev_support/samples/account.json
Add timestamp to filename? (Y/n): Y
Use compact JSON format? (y/N): N
```

---

## Option 3: Rich Prompts (Built-in Rich)

**Pros**: No new dependencies, already using Rich, consistent styling  
**Cons**: Less interactive features, no form grouping, manual validation

### Example Implementation

```python
# importer/interactive.py
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.console import Console
from pathlib import Path

console = Console()

def prompt_fetch_interactive():
    """Interactive prompts for fetch command."""
    console.print("\n[bold cyan]dbt Cloud Importer - Interactive Mode[/bold cyan]\n")
    
    # Credentials
    account_id = IntPrompt.ask(
        "Account ID",
        default=get_settings().account_id or None
    )
    
    token = Prompt.ask(
        "API Token",
        password=True,
        default=get_settings().api_token or None
    )
    
    host = Prompt.ask(
        "Host URL",
        default=get_settings().host or "https://cloud.getdbt.com"
    )
    
    # Options
    output_str = Prompt.ask(
        "Output file path (optional)",
        default="dev_support/samples/account.json"
    )
    output_path = Path(output_str) if output_str else None
    
    auto_timestamp = Confirm.ask(
        "Add timestamp to filename?",
        default=True
    )
    
    compact = Confirm.ask(
        "Use compact JSON format?",
        default=False
    )
    
    return {
        "account_id": account_id,
        "token": token,
        "host": host,
        "output": output_path,
        "auto_timestamp": auto_timestamp,
        "compact": compact,
    }
```

**Visual Output**:
```
dbt Cloud Importer - Interactive Mode

Account ID [12345]: 12345
API Token: ********
Host URL [https://cloud.getdbt.com]: https://cloud.getdbt.com
Output file path (optional) [dev_support/samples/account.json]: 
Add timestamp to filename? [Y/n]: Y
Use compact JSON format? [y/N]: N
```

---

## Option 4: Textual (Full TUI Framework)

**Pros**: Most powerful, full terminal UI, Rich integration, can build complex interfaces  
**Cons**: Overkill for simple forms, steeper learning curve, more code

### Example Implementation

```python
# importer/interactive_fetch_app.py
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Label, Checkbox, Header, Footer
from textual.binding import Binding

class FetchInteractiveApp(App):
    """Textual TUI for fetch command."""
    
    CSS = """
    Container {
        padding: 1;
    }
    Input {
        margin: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+s", "submit", "Submit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Label("Account ID:", classes="label")
            yield Input(placeholder="12345", id="account_id")
            yield Label("API Token:", classes="label")
            yield Input(placeholder="your_token", password=True, id="token")
            yield Label("Host URL:", classes="label")
            yield Input(placeholder="https://cloud.getdbt.com", id="host")
            yield Label("Output Path:", classes="label")
            yield Input(placeholder="dev_support/samples/account.json", id="output")
            yield Checkbox("Add timestamp", True, id="auto_timestamp")
            yield Checkbox("Compact JSON", False, id="compact")
        with Horizontal():
            yield Button("Submit", variant="primary", id="submit")
            yield Button("Cancel", variant="error", id="cancel")
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.action_submit()
        else:
            self.exit()
    
    def action_submit(self) -> None:
        account_id = self.query_one("#account_id", Input).value
        token = self.query_one("#token", Input).value
        host = self.query_one("#host", Input).value
        output = self.query_one("#output", Input).value
        auto_timestamp = self.query_one("#auto_timestamp", Checkbox).value
        compact = self.query_one("#compact", Checkbox).value
        
        self.exit({
            "account_id": account_id,
            "token": token,
            "host": host,
            "output": output,
            "auto_timestamp": auto_timestamp,
            "compact": compact,
        })
```

**Visual Output**:
```
┌─────────────────────────────────────────┐
│ dbt Cloud Importer - Fetch              │
├─────────────────────────────────────────┤
│                                         │
│  Account ID:                            │
│  [12345________________]                │
│                                         │
│  API Token:                             │
│  [****************]                    │
│                                         │
│  Host URL:                              │
│  [https://cloud.getdbt.com]            │
│                                         │
│  Output Path:                           │
│  [dev_support/samples/account.json]    │
│                                         │
│  ☑ Add timestamp                       │
│  ☐ Compact JSON                         │
│                                         │
│  [Submit]  [Cancel]                     │
└─────────────────────────────────────────┘
```

---

## Option 5: SimpleMenu (Custom with Rich)

**Pros**: Full control, no dependencies, matches existing style  
**Cons**: More code to maintain, manual implementation

### Example Implementation

```python
# importer/interactive.py
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

console = Console()

def show_menu(title: str, options: list[tuple[str, str]]) -> str:
    """Display a numbered menu and return selection."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    for i, (key, desc) in enumerate(options, 1):
        table.add_row(f"[cyan]{i}[/cyan]", desc)
    
    console.print(Panel(table, title=title, border_style="cyan"))
    
    while True:
        choice = Prompt.ask(f"\nSelect option (1-{len(options)})")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        console.print("[red]Invalid selection[/red]")

def prompt_fetch_interactive():
    """Interactive prompts for fetch command."""
    console.print(Panel.fit(
        "[bold cyan]dbt Cloud Importer - Interactive Mode[/bold cyan]",
        border_style="cyan"
    ))
    
    # Menu for command selection
    command = show_menu("Select Command", [
        ("fetch", "Fetch account data"),
        ("normalize", "Normalize JSON to YAML"),
    ])
    
    if command == "fetch":
        # Fetch-specific prompts
        account_id = Prompt.ask("Account ID", default=str(get_settings().account_id or ""))
        token = Prompt.ask("API Token", password=True)
        # ... rest of prompts
    
    return {...}
```

**Visual Output**:
```
┌─────────────────────────────────────┐
│ dbt Cloud Importer - Interactive Mode│
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Select Command                      │
├─────────────────────────────────────┤
│ 1  Fetch account data               │
│ 2  Normalize JSON to YAML           │
└─────────────────────────────────────┘

Select option (1-2): 1
```

---

## Comparison Matrix

| Feature | InquirerPy | Questionary | Rich Prompts | Textual | Custom Menu |
|---------|-----------|-------------|--------------|---------|-------------|
| **Dependencies** | New | New | None (built-in) | New | None |
| **Form-like UI** | ✅ Excellent | ⚠️ Basic | ❌ No | ✅ Excellent | ⚠️ Manual |
| **File Browser** | ✅ Built-in | ⚠️ Basic | ❌ No | ✅ Full TUI | ❌ Manual |
| **Multi-select** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes | ⚠️ Manual |
| **Validation** | ✅ Built-in | ✅ Built-in | ⚠️ Manual | ✅ Built-in | ⚠️ Manual |
| **Rich Integration** | ✅ Good | ⚠️ Limited | ✅ Native | ✅ Native | ✅ Native |
| **Learning Curve** | Medium | Low | Low | High | Medium |
| **Code Complexity** | Medium | Low | Low | High | Medium |
| **Similarity to `huh`** | ✅ Very similar | ⚠️ Similar | ❌ Different | ✅ Similar | ❌ Different |

---

## Recommendation

**InquirerPy** is recommended because:
1. Most similar to `dbtcloud-terraforming`'s `huh` library
2. Form-based interface matches user expectations
3. Good balance of features without over-engineering
4. Works well with Rich for consistent styling
5. Active maintenance and good documentation

**Questionary** is a good alternative if you want something simpler and lighter-weight, but it's less form-like and has fewer features.

**Rich Prompts** is best if you want zero new dependencies, but you'll need to build form-like interfaces manually.

**Textual** is overkill for simple forms but excellent if you want to build a full terminal application later.

---

## What Other Projects Use

### ProxmoxVE Helper Scripts (Bash/Shell)

**Language**: 89.7% Shell, 9.7% TypeScript  
**Approach**: Uses native shell tools - `dialog`, `whiptail`, or custom `select` statements

**Example Pattern** (typical bash approach):
```bash
#!/bin/bash

# Using dialog (if available)
dialog --menu "Select option:" 15 40 4 \
  1 "Fetch account data" \
  2 "Normalize JSON to YAML" \
  3 "Exit" 2> /tmp/menu_choice

choice=$(cat /tmp/menu_choice)

# Or using select (simpler, no dependencies)
PS3="Select option: "
select opt in "Fetch" "Normalize" "Exit"; do
  case $opt in
    "Fetch") echo "Fetching..."; break;;
    "Normalize") echo "Normalizing..."; break;;
    "Exit") exit;;
  esac
done

# Simple prompts
read -p "Account ID: " account_id
read -sp "API Token: " token  # -s hides input
```

**Pros**: Zero dependencies, works everywhere  
**Cons**: Limited styling, no form grouping, basic validation

### Deployrr (PHP)

**Language**: 83.9% PHP, 16.1% Shell  
**Approach**: PHP CLI with `readline` functions or custom echo/read loops

**Example Pattern** (typical PHP CLI approach):
```php
<?php
// Simple menu loop
function showMenu() {
    echo "\n=== dbt Cloud Importer ===\n";
    echo "1. Fetch account data\n";
    echo "2. Normalize JSON to YAML\n";
    echo "3. Exit\n";
    echo "Choice: ";
}

$choice = readline();
switch($choice) {
    case '1':
        $account_id = readline("Account ID: ");
        $token = readline("API Token: ");
        // ... execute fetch
        break;
    case '2':
        // ... normalize flow
        break;
}

// Or using readline with history
$account_id = readline("Account ID: ");
readline_add_history($account_id);  // Save to history
```

**Pros**: Built into PHP, simple  
**Cons**: Very basic, no advanced features, limited styling

### Why Python Projects Use Libraries

Unlike shell/PHP scripts, Python projects typically use libraries because:
1. **Better UX**: Form-like interfaces, validation, file browsers
2. **Cross-platform**: Works consistently across OSes
3. **Rich features**: Multi-select, conditional fields, themes
4. **Maintainability**: Less code, better abstractions

Shell/PHP projects use native tools because:
- They're already shell/PHP - no language barrier
- Simpler deployment (no package managers needed)
- Different use case (system scripts vs. user-facing tools)

