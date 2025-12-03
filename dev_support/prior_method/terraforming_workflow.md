# Migrating customers with dbtcloud-terraforming and Terraform

# Tools

[Terraform provider](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest) - the TF provider to update dbt Cloud config

[dbtcloud-terraforming](https://github.com/dbt-labs/dbtcloud-terraforming) - a tool that can be used to generated Terraform config based of existing dbt Cloud config

# Process

## What can’t be migrated with the tools

- secrets/passwords (there is a mechanism for people to provide it themselves)
- job history and logs
- audit logs
- code from managed repos (in that case people should save it in their own git provider beforehand)
- developers credentials
- code that is saved but not committed
- anything that can’t be set via the Terraform provider
    - SSO / git integration
- (experimental) `dbtcloud-terraforming` would work best with SSO group mapping. Assigning users to groups by hand/API is quite experimental

## Steps to migrate a customer

### Pre-req

- Current account / Decisions
    - ask the customer to give you an account-wide read-only token to be able to download the existing config
    - get the list of projects to migrate (if not all)
    - decide if jobs should be created deactivated or not in the new platform
        - with one customer they wanted me to create all jobs deactivated and then were going to activate/deactivate them in the new and old account, by hand
- New account set up by the customer
    - manually set up all integrations (SSO, git, Slack etc…)
    - in case IP restrictions is in place in the DW, allow the new IPs
    - requests all PL connections if they are using PL
    - create a service token with an account-admin scope

### Prep (by dbt Labs) (TODO @Benoit Perigaud add video of walkthrough)

- Check [dbtcloud-terraforming](https://github.com/dbt-labs/dbtcloud-terraforming)’s README and install it (`brew install dbtcloud-terraforming`)
    - the tool has 3 main commands, `generate` to generate the config, `import` to generate import blocks and `genimport` to generate both the config and import blocks
        - `import` / `genimport` only needs to be used to load existing resources into state (e.g. to start managing existing resources via Terraform going forward). To create new resources in a new account (e.g. for a migration), `generate` is the command you need/want
    - the tool accepts parameters (see README), but can also be run in interactive mode with `dbtcloud-teraforming interactive` so that you can pick the different parameters required via an interface

- For migrating a customer, you will likely want to use the following command:
    
    ```
    dbtcloud-terraforming generate --resource-types all --linked-resource-types all --projects 1,2,3 --output out.tf --parameterize-jobs
    ```
    
    - if you want to exclude `dbtcloud_user_groups` (because the customer uses SSO group mappings), you could add `--exclude-resource-types dbtcloud_user_groups`
- this will generate a file [`out.tf`](http://out.tf) with the required configuration. To use it, remove all the commented lines (like `dbtcloud_repository_github_installation_id_xxxx = ""`) to set up the variables and move those, uncommented, to a new file called `terraform.tfvars`
    - tweak the `locals` block for jobs to suit your needs
- then, do a `terraform plan` to see if there is any issue. If there are issues, try to fix those.
- Finally share the following files with the customer
    - the variable definitions (the ones starting with `var {...}` in the generated output) that will contains descriptions of the different variables and links to their current accounts
    - the `terraform.tfvars`
    
    and ask them to populate every single variable in `terraform.tfvars` (those will be the secrets required)
    

### On the day ([example of call with a customer](https://us-13442.app.gong.io/e/c-share/?tkn=1ojsu0u4zrwlu5enqaiw8211c))

- share the Terraform config with the customer (you could technically re-run the `dbtcloud-terraforming` command just at that time as long as no new var is required)
- make sure that the [dbtcloud Terraform provider](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest) is configured to be pointing to the new account
- use the account admin token created before (or a new one) and do a `terraform plan` (hopefully no error), followed by a `terraform apply` and cross fingers very hard
    - if there are any errors with `terraform apply` that didn’t appear with `terraform plan` it will likely be because the generated config has a few issues (maybe hard coded IDs or resources that just can’t be created) and those would need to be fixed before `apply` correctly works — the call shows how we solved some of those live

### Optional

- it would be possible to also provide them other Terraform files for the current account if they want to deactivate some of or all the jobs
    - in that case, re-run `dbtcloud-terraforming` with the following settings
        - command: `genimport` (so we can modify existing jobs)
        - just for the `dbtcloud_job` resource
        - without linked resources
        - and with `--parametrize-jobs` active
    - then, doing a `terraform plan` should show that the only things changing would be the schedule and/or triggers

## Post migration-steps

- For their developers
    - all their developers will need to either be re-invited or re-invite themselves by going to the SSO url and activating their email
    - all developers will need to
        - reconnect their git account if using native git integration
        - setup signed commits if they use them
        - set again their credentials for all their projects
    - developers will need to commit in the old account all the code they want to be able to continue working on in the new account
- For external integrations
    - they will need to update all applications that call the dbt Cloud APIs (trigger job, maintain users, etc…) to point to the new account
        - for jobs, they might have to point to all the new Job IDs as well
            - you can retrieve the list of all old IDs vs new IDs by installing `jq` and running this script:
            
            ```
            cat  terraform.tfstate | jq '[.resources[] | select(.type == "dbtcloud_job") | {"old_id": .name | split("_")[-1], "new_id": .instances[0].attributes.id}]'
            ```
            
- Decide with the customer when the old account can be blocked and/or turned off
    - the support team can help lock an account if we reach out to them