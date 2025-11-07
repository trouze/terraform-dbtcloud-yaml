## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| <a name="provider_dbtcloud"></a> [dbtcloud](#provider\_dbtcloud) | 1.3.0 |
| <a name="provider_null"></a> [null](#provider\_null) | 3.2.4 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [dbtcloud_repository.repository](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/repository) | resource |
| [null_resource.validation](https://registry.terraform.io/providers/hashicorp/null/latest/docs/resources/resource) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the dbt Cloud project this repository is associated with | `string` | n/a | yes |
| <a name="input_repository_data"></a> [repository\_data](#input\_repository\_data) | Repository configuration object with auto-detection and validation.<br/><br/>Supported providers (auto-detected from remote\_url):<br/>  - GitHub: https://github.com/* or git@github.com:* (supports github\_app strategy)<br/>  - GitLab: https://gitlab.com/* or git@gitlab.com:* (supports deploy\_token strategy)<br/>  - Azure DevOps: https://dev.azure.com/* or git@ssh.dev.azure.com:* (supports azure\_active\_directory\_app strategy)<br/>  - Bitbucket: https://bitbucket.org/* (uses deploy\_key strategy)<br/>  - Generic: Any other URL (uses deploy\_key strategy)<br/><br/>Required fields:<br/>  - remote\_url: Git repository URL (HTTPS or SSH)<br/><br/>Optional fields depend on git\_clone\_strategy:<br/>  - git\_clone\_strategy: Auto-detected, but can be explicitly set to:<br/>      * deploy\_key (default for all providers)<br/>      * github\_app (GitHub only, requires github\_installation\_id)<br/>      * deploy\_token (GitLab only, requires gitlab\_project\_id)<br/>      * azure\_active\_directory\_app (Azure DevOps only, requires azure\_active\_directory\_project\_id and azure\_active\_directory\_repository\_id)<br/>  <br/>  - github\_installation\_id: (GitHub app integration only) Integer ID of GitHub App installation<br/>  - gitlab\_project\_id: (GitLab integration only) Integer ID of GitLab project<br/>  - azure\_active\_directory\_project\_id: (Azure DevOps only) UUID of Azure DevOps project<br/>  - azure\_active\_directory\_repository\_id: (Azure DevOps only) UUID of Azure DevOps repository<br/>  - azure\_bypass\_webhook\_registration\_failure: (Azure DevOps only) Boolean, default false<br/>  <br/>  - is\_active: Boolean, default true<br/>  - private\_link\_endpoint\_id: Optional private link endpoint ID (all providers)<br/>  - pull\_request\_url\_template: Optional custom PR URL template (all providers)<br/><br/>Example GitHub with GitHub App:<br/>  repository = {<br/>    remote\_url = "https://github.com/myorg/myrepo.git"<br/>    git\_clone\_strategy = "github\_app"<br/>    github\_installation\_id = 12345678<br/>  }<br/><br/>Example GitLab with Deploy Token:<br/>  repository = {<br/>    remote\_url = "https://gitlab.com/mygroup/myproject.git"<br/>    git\_clone\_strategy = "deploy\_token"<br/>    gitlab\_project\_id = 9876543<br/>  }<br/><br/>Example Azure DevOps:<br/>  repository = {<br/>    remote\_url = "https://dev.azure.com/myorg/myproject/_git/myrepo"<br/>    git\_clone\_strategy = "azure\_active\_directory\_app"<br/>    azure\_active\_directory\_project\_id = "550e8400-e29b-41d4-a716-446655440000"<br/>    azure\_active\_directory\_repository\_id = "550e8400-e29b-41d4-a716-446655440001"<br/>  }<br/><br/>Example Generic (SSH Deploy Key):<br/>  repository = {<br/>    remote\_url = "git@github.com:myorg/myrepo.git"<br/>  } | `any` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_project_repository_id"></a> [project\_repository\_id](#output\_project\_repository\_id) | n/a |
| <a name="output_repository_id"></a> [repository\_id](#output\_repository\_id) | n/a |
