# Examples are end-user starter code, not module source — skip all linting.
rule "terraform_required_version" { enabled = false }
rule "terraform_required_providers" { enabled = false }
rule "terraform_documented_variables" { enabled = false }
rule "terraform_documented_outputs" { enabled = false }
rule "terraform_naming_convention" { enabled = false }
rule "terraform_comment_syntax" { enabled = false }
rule "terraform_unused_declarations" { enabled = false }
rule "terraform_unused_required_providers" { enabled = false }
rule "terraform_standard_module_structure" { enabled = false }
