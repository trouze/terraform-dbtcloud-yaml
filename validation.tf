#############################################
# YAML Configuration Validation
#
# Collects all configuration errors and reports
# them together at plan time via terraform_data.validate_yaml_config
# in main.tf. Add new checks here as _errors_* locals.
#############################################

locals {
  # ── Index locals: pre-computed key sets for cross-reference lookups ────────

  _valid_global_connection_keys = toset([
    for c in try(local.yaml_content.global_connections, []) : try(c.key, c.name)
  ])

  _valid_project_keys = toset([
    for p in local.projects : try(p.key, p.name)
  ])

  _valid_group_keys = toset([
    for g in try(local.yaml_content.groups, []) : try(g.key, g.name)
  ])

  # Environment keys per project: { project_key => set(env_key) }
  _env_keys_by_project = {
    for p in local.projects :
    try(p.key, p.name) => toset([
      for e in try(p.environments, []) : try(e.key, e.name)
    ])
  }

  # Job keys per project: { project_key => set(job_key) }
  _job_keys_by_project = {
    for p in local.projects :
    try(p.key, p.name) => toset([
      for j in try(p.jobs, []) : try(j.key, j.name)
    ])
  }

  # Effective artefact job refs (COMPAT v1 artefacts vs v2 project_artefacts; same rules as modules/project_artefacts)
  _artefact_docs_job_by_project = {
    for p in local.projects :
    try(p.key, p.name) => (
      try(p.project_artefacts.docs_job_key, null) != null && try(tostring(p.project_artefacts.docs_job_key), "") != ""
      ? p.project_artefacts.docs_job_key
      : try(p.artefacts.docs_job, null)
    )
  }

  _artefact_freshness_job_by_project = {
    for p in local.projects :
    try(p.key, p.name) => (
      try(p.project_artefacts.freshness_job_key, null) != null && try(tostring(p.project_artefacts.freshness_job_key), "") != ""
      ? p.project_artefacts.freshness_job_key
      : try(p.artefacts.freshness_job, null)
    )
  }

  # Extended attribute keys per project: { project_key => set(ea_key) }
  _ea_keys_by_project = {
    for p in local.projects :
    try(p.key, p.name) => toset([
      for ea in try(p.extended_attributes, []) : try(ea.key, ea.name)
    ])
  }

  # Profile keys per project: { project_key => set(profile_key) }
  _profile_keys_by_project = {
    for p in local.projects :
    try(p.key, p.name) => toset([
      for prof in try(p.profiles, []) : try(prof.key, prof.name)
    ])
  }

  _valid_credential_types = toset([
    "databricks", "snowflake", "bigquery", "redshift", "postgres",
    "athena", "fabric", "synapse", "starburst", "trino",
    "spark", "apache_spark", "teradata",
  ])

  _valid_connection_types = toset([
    "databricks", "snowflake", "bigquery", "redshift", "postgres",
    "spark", "starburst", "starburst_trino", "apache_spark", "athena", "fabric", "synapse", "teradata", "salesforce",
  ])

  _privatelink_endpoint_keys = toset([
    for ple in try(local.yaml_content.privatelink_endpoints, []) : try(ple.key, ple.name)
  ])

  # ── V-00: environments need connection (or connection_key) or primary_profile_key ─

  _errors_env_connection_or_profile = flatten([
    for p in local.projects : [
      for env in try(p.environments, []) :
      (
        (
          try(env.connection, null) == null && try(env.connection_key, null) == null
          ) && (
          try(env.primary_profile_key, null) == null || try(env.primary_profile_key, "") == ""
        )
        ) ? [
        "Environment '${try(env.key, env.name)}' in project '${try(p.key, p.name)}' must set connection or connection_key, or set primary_profile_key to a profiles[].key (v2/importer)."
      ] : []
    ]
  ])

  # ── V-00b: primary_profile_key → profiles[].key (same project) ─────────────

  _errors_primary_profile_key = flatten([
    for p in local.projects : [
      for env in try(p.environments, []) :
      try(
        env.primary_profile_key != null && env.primary_profile_key != "" && !contains(
          try(local._profile_keys_by_project[try(p.key, p.name)], toset([])),
          env.primary_profile_key
        )
        ? ["Environment '${try(env.key, env.name)}' in project '${try(p.key, p.name)}' references primary_profile_key '${env.primary_profile_key}' but no profile with that key exists. Available profile keys: [${join(", ", tolist(try(local._profile_keys_by_project[try(p.key, p.name)], toset([]))))}]"]
        : [],
        []
      )
    ]
  ])

  # ── V-01: connection / connection_key in environments → global_connections[].key (skip LOOKUP:… — resolved via module.data_lookups)

  _errors_connection_key = flatten([
    for p in local.projects : [
      for env in try(p.environments, []) :
      try(
        (
          # v2: connection is omitted when primary_profile_key supplies connection via profile
          try(env.primary_profile_key, null) == null || try(env.primary_profile_key, "") == ""
          ) && (
          (try(env.connection, null) != null ? env.connection : try(env.connection_key, null)) != null &&
          !startswith(tostring(try(env.connection, null) != null ? env.connection : try(env.connection_key, null)), "LOOKUP:") &&
          !contains(local._valid_global_connection_keys, try(env.connection, null) != null ? env.connection : try(env.connection_key, null))
        )
        ? ["Environment '${try(env.key, env.name)}' in project '${try(p.key, p.name)}' references connection '${try(env.connection, null) != null ? env.connection : try(env.connection_key, null)}' but no global_connection with that key exists. Available keys: [${join(", ", tolist(local._valid_global_connection_keys))}]"]
        : [],
        []
      )
    ]
  ])

  # ── V-01b: connection_key on profiles → global_connections[].key (skip LOOKUP:…)

  _errors_profile_connection_key = flatten([
    for p in local.projects : [
      for prof in try(p.profiles, []) :
      try(
        try(prof.connection_key, null) != null &&
        !startswith(tostring(prof.connection_key), "LOOKUP:") &&
        !contains(local._valid_global_connection_keys, prof.connection_key)
        ? ["Profile '${try(prof.key, prof.name)}' in project '${try(p.key, p.name)}' references connection_key '${prof.connection_key}' but no global_connection with that key exists. Available keys: [${join(", ", tolist(local._valid_global_connection_keys))}]"]
        : [],
        []
      )
    ]
  ])

  # ── V-01c: extended_attributes_key on profiles → extended_attributes[].key

  _errors_profile_ea_key = flatten([
    for p in local.projects : [
      for prof in try(p.profiles, []) :
      try(
        prof.extended_attributes_key != null && prof.extended_attributes_key != "" && !contains(
          try(local._ea_keys_by_project[try(p.key, p.name)], toset([])),
          prof.extended_attributes_key
        )
        ? ["Profile '${try(prof.key, prof.name)}' in project '${try(p.key, p.name)}' references extended_attributes_key '${prof.extended_attributes_key}' but no extended_attribute with that key exists. Available keys: [${join(", ", tolist(try(local._ea_keys_by_project[try(p.key, p.name)], toset([]))))}]"]
        : [],
        []
      )
    ]
  ])

  # ── V-02: environment_key in jobs → environments[].key (same project) ──────

  _errors_job_env_key = flatten([
    for p in local.projects : [
      for job in try(p.jobs, []) : (
        try(job.environment_key, null) != null &&
        !contains(
          try(local._env_keys_by_project[try(p.key, p.name)], toset([])),
          job.environment_key
        )
        ) ? [
        "Job '${try(job.key, job.name)}' in project '${try(p.key, p.name)}' references environment_key '${job.environment_key}' which is not defined in this project's environments. Available keys: [${join(", ", tolist(try(local._env_keys_by_project[try(p.key, p.name)], toset([]))))}]"
      ] : []
    ]
  ])

  # ── V-03: extended_attributes_key in environments → extended_attributes[].key

  _errors_ea_key = flatten([
    for p in local.projects : [
      for env in try(p.environments, []) :
      try(
        env.extended_attributes_key != null && env.extended_attributes_key != "" && !contains(
          try(local._ea_keys_by_project[try(p.key, p.name)], toset([])),
          env.extended_attributes_key
        )
        ? ["Environment '${try(env.key, env.name)}' in project '${try(p.key, p.name)}' references extended_attributes_key '${env.extended_attributes_key}' but no extended_attribute with that key exists. Available keys: [${join(", ", tolist(try(local._ea_keys_by_project[try(p.key, p.name)], toset([]))))}]"]
        : [],
        []
      )
    ]
  ])

  # ── V-03b: each extended_attributes[] must supply v1 content or v2 extended_attributes object (non-empty)

  _errors_ea_payload = flatten([
    for p in local.projects : [
      for ea in try(p.extended_attributes, []) :
      (
        (try(ea.extended_attributes, null) == null || length(keys(try(ea.extended_attributes, {}))) == 0) &&
        (try(ea.content, null) == null || length(keys(try(ea.content, {}))) == 0)
        ) ? [
        "Project '${try(p.key, p.name)}' extended_attributes entry '${try(ea.key, ea.name)}' must set non-empty 'content' (v1) or 'extended_attributes' (v2/importer)."
      ] : []
    ]
  ])

  # ── V-04: deferring_environment_key in jobs → environments[].key ───────────

  _errors_deferring_env_key = flatten([
    for p in local.projects : [
      for job in try(p.jobs, []) :
      try(
        job.deferring_environment_key != null && !contains(
          try(local._env_keys_by_project[try(p.key, p.name)], toset([])),
          job.deferring_environment_key
        )
        ? ["Job '${try(job.key, job.name)}' in project '${try(p.key, p.name)}' has deferring_environment_key '${job.deferring_environment_key}' but that environment does not exist. Available keys: [${join(", ", tolist(try(local._env_keys_by_project[try(p.key, p.name)], toset([]))))}]"]
        : [],
        []
      )
    ]
  ])

  # ── V-05: artefacts / project_artefacts job keys → jobs[].key (COMPAT v1 vs v2/importer names)

  _errors_artefact_job_keys = flatten([
    for p in local.projects :
    try(p.artefacts, null) != null || try(p.project_artefacts, null) != null
    ? concat(
      local._artefact_docs_job_by_project[try(p.key, p.name)] != null && !contains(
        try(local._job_keys_by_project[try(p.key, p.name)], toset([])),
        local._artefact_docs_job_by_project[try(p.key, p.name)]
        ) ? [
        "Project '${try(p.key, p.name)}' artefacts / project_artefacts docs job references key '${local._artefact_docs_job_by_project[try(p.key, p.name)]}' which does not exist. Available job keys: [${join(", ", tolist(try(local._job_keys_by_project[try(p.key, p.name)], toset([]))))}]"
      ] : [],
      local._artefact_freshness_job_by_project[try(p.key, p.name)] != null && !contains(
        try(local._job_keys_by_project[try(p.key, p.name)], toset([])),
        local._artefact_freshness_job_by_project[try(p.key, p.name)]
        ) ? [
        "Project '${try(p.key, p.name)}' artefacts / project_artefacts freshness job references key '${local._artefact_freshness_job_by_project[try(p.key, p.name)]}' which does not exist. Available job keys: [${join(", ", tolist(try(local._job_keys_by_project[try(p.key, p.name)], toset([]))))}]"
      ] : [],
    )
    : []
  ])

  # ── V-05b: semantic_layer / semantic_layer_config must resolve an environment ─

  _errors_semantic_layer_env = flatten([
    for p in local.projects :
    try(p.semantic_layer, null) != null || try(p.semantic_layer_config, null) != null
    ? (
      try(p.semantic_layer_config.environment_id, null) != null
      ? []
      : length(compact([
        try(p.semantic_layer_config.environment_key, null),
        try(p.semantic_layer_config.environment, null),
        try(p.semantic_layer.environment_key, null),
        try(p.semantic_layer.environment, null),
      ])) == 0
      ? ["Project '${try(p.key, p.name)}' has semantic_layer or semantic_layer_config but no environment_id (v2) and no environment_key / environment to resolve against environments[].key."]
      : !contains(
        try(local._env_keys_by_project[try(p.key, p.name)], toset([])),
        coalesce(
          try(p.semantic_layer_config.environment_key, null),
          try(p.semantic_layer_config.environment, null),
          try(p.semantic_layer.environment_key, null),
          try(p.semantic_layer.environment, null)
        )
        ) ? [
        "Project '${try(p.key, p.name)}' semantic layer references environment '${coalesce(try(p.semantic_layer_config.environment_key, null), try(p.semantic_layer_config.environment, null), try(p.semantic_layer.environment_key, null), try(p.semantic_layer.environment, null))}' which does not exist. Available environment keys: [${join(", ", tolist(try(local._env_keys_by_project[try(p.key, p.name)], toset([]))))}]"
      ] : []
    )
    : []
  ])

  # ── V-06: Every project must have a name ──────────────────────────────────

  _errors_project_name = [
    for p in local.projects :
    "A project entry is missing the required 'name' field."
    if try(p.name, null) == null
  ]

  # ── V-07: type=deployment environments must have deployment_type ───────────

  _errors_deployment_type = flatten([
    for p in local.projects : [
      for env in try(p.environments, []) :
      "Environment '${try(env.key, env.name)}' in project '${try(p.key, p.name)}' has type 'deployment' but is missing deployment_type. Set deployment_type to one of: [production, staging, other]"
      if try(env.type, "development") == "deployment" && try(env.deployment_type, null) == null
    ]
  ])

  # ── V-08: execute_steps must be non-empty ─────────────────────────────────

  _errors_execute_steps = flatten([
    for p in local.projects : [
      for job in try(p.jobs, []) :
      "Job '${try(job.key, job.name)}' in project '${try(p.key, p.name)}' has an empty execute_steps list. At least one dbt command is required (e.g. 'dbt build')."
      if length(try(job.execute_steps, [])) == 0
    ]
  ])

  # ── V-09: inline credential.credential_type must be a valid warehouse type ─

  _errors_credential_type = flatten([
    for p in local.projects : [
      for env in try(p.environments, []) :
      try(
        env.credential.credential_type != null && !contains(local._valid_credential_types, env.credential.credential_type)
        ? ["Environment '${try(env.key, env.name)}' in project '${try(p.key, p.name)}' has credential_type '${env.credential.credential_type}' which is not a recognized warehouse type. Valid types: [${join(", ", tolist(local._valid_credential_types))}]"]
        : [],
        []
      )
    ]
  ])

  # ── V-10: global_connections[].type must be a valid warehouse type ─────────

  _errors_connection_type = [
    for conn in try(local.yaml_content.global_connections, []) :
    "Global connection '${try(conn.key, conn.name)}' has type '${try(conn.type, "")}' which is not a recognized warehouse type. Valid types: [${join(", ", tolist(local._valid_connection_types))}]"
    if !contains(local._valid_connection_types, try(conn.type, ""))
  ]

  # ── V-10b: global_connections[].private_link_endpoint_key → privatelink_endpoints[].key ─

  _errors_connection_privatelink_key = [
    for conn in try(local.yaml_content.global_connections, []) :
    "Global connection '${try(conn.key, conn.name)}' references private_link_endpoint_key '${conn.private_link_endpoint_key}' but no privatelink_endpoints[] entry has that key. Define privatelink_endpoints at the YAML root or set private_link_endpoint_id."
    if(
      try(conn.private_link_endpoint_key, null) != null &&
      try(conn.private_link_endpoint_id, null) == null &&
      !contains(local._privatelink_endpoint_keys, conn.private_link_endpoint_key)
    )
  ]

  # ── V-10c: project.repository.private_link_endpoint_key → privatelink_endpoints[].key ─

  _errors_repository_privatelink_key = [
    for p in local.projects :
    "Project '${try(p.key, p.name)}' repository references private_link_endpoint_key '${p.repository.private_link_endpoint_key}' but no privatelink_endpoints[] entry has that key. Define privatelink_endpoints at the YAML root or set private_link_endpoint_id."
    if(
      try(p.repository, null) != null &&
      try(p.repository.private_link_endpoint_key, null) != null &&
      try(p.repository.private_link_endpoint_id, null) == null &&
      !contains(local._privatelink_endpoint_keys, p.repository.private_link_endpoint_key)
    )
  ]

  # ── V-11: schedule coherence — schedule:true requires schedule_type or cron ─

  _errors_schedule_config = flatten([
    for p in local.projects : [
      for job in try(p.jobs, []) :
      "Job '${try(job.key, job.name)}' in project '${try(p.key, p.name)}' has triggers.schedule = true but no schedule_type or schedule_cron is set. Add schedule_type (e.g. 'days_of_week') and matching schedule_hours, or use schedule_cron with a cron expression."
      if(
        try(job.triggers.schedule, false) == true &&
        try(job.schedule_type, null) == null &&
        try(job.schedule_cron, null) == null
      )
    ]
  ])

  # ── V-12: user_groups[].group_keys → groups[].key ─────────────────────────

  _errors_user_group_keys = flatten([
    for ug in try(local.yaml_content.user_groups, []) : [
      for gk in try(ug.group_keys, []) :
      "user_groups entry for user_id ${try(ug.user_id, "unknown")} references group_key '${gk}' but no group with that key is defined. Available group keys: [${join(", ", tolist(local._valid_group_keys))}]"
      if !contains(local._valid_group_keys, gk)
    ]
  ])

  # ── V-13: service_token permission project_key → projects[].key ────────────
  # Align with modules/service_tokens COMPAT: prefer service_token_permissions[] when non-empty.

  _errors_service_token_project_keys = flatten([
    for st in try(local.yaml_content.service_tokens, []) : [
      for perm in(
        length(try(st.service_token_permissions, [])) > 0 ? try(st.service_token_permissions, []) : try(st.permissions, [])
      ) :
      "Service token '${try(st.key, st.name)}' has a permission referencing project_key '${perm.project_key}' which is not a defined project. Available project keys: [${join(", ", tolist(local._valid_project_keys))}]"
      if(
        try(perm.project_key, null) != null &&
        !contains(local._valid_project_keys, perm.project_key)
      )
    ]
  ])

  # ── Aggregated error list ──────────────────────────────────────────────────

  _all_validation_errors = compact(concat(
    local._errors_env_connection_or_profile,
    local._errors_primary_profile_key,
    local._errors_connection_key,
    local._errors_profile_connection_key,
    local._errors_profile_ea_key,
    local._errors_job_env_key,
    local._errors_ea_key,
    local._errors_ea_payload,
    local._errors_deferring_env_key,
    local._errors_artefact_job_keys,
    local._errors_semantic_layer_env,
    local._errors_project_name,
    local._errors_deployment_type,
    local._errors_execute_steps,
    local._errors_credential_type,
    local._errors_connection_type,
    local._errors_connection_privatelink_key,
    local._errors_repository_privatelink_key,
    local._errors_schedule_config,
    local._errors_user_group_keys,
    local._errors_service_token_project_keys,
  ))
}

#############################################
# Best-Practice Warnings (check blocks)
#
# These produce warnings at plan/apply time but do NOT block apply.
# They catch common configuration patterns that work but may be unintentional.
#############################################

# ── C-01: Production environments without protected: true ─────────────────────
# A 'terraform destroy' on an unprotected production environment removes it
# along with all its history and job links.

check "production_environments_protected" {
  assert {
    condition = length(flatten([
      for p in local.projects : [
        for env in try(p.environments, []) :
        "${try(p.key, p.name)}/${try(env.key, env.name)}"
        if try(env.deployment_type, null) == "production" && !try(env.protected, false)
      ]
    ])) == 0
    error_message = "Best practice: the following production environments have protected: false and could be accidentally deleted by 'terraform destroy'. Add protected: true to prevent this. Environments: ${join(", ", flatten([for p in local.projects : [for env in try(p.environments, []) : "${try(p.key, p.name)}/${try(env.key, env.name)}" if try(env.deployment_type, null) == "production" && !try(env.protected, false)]]))}"
  }
}

# ── C-02: Schedule config set but triggers.schedule is false ──────────────────
# schedule_type, schedule_cron, schedule_hours, and schedule_days are silently
# ignored when triggers.schedule is false — the job simply won't run on a schedule.

check "schedule_config_without_trigger" {
  assert {
    condition = length(flatten([
      for p in local.projects : [
        for job in try(p.jobs, []) :
        "'${try(job.key, job.name)}' in project '${try(p.key, p.name)}'"
        if !try(job.triggers.schedule, false) && (
          try(job.schedule_type, null) != null ||
          try(job.schedule_cron, null) != null
        )
      ]
    ])) == 0
    error_message = "Best practice: the following jobs have schedule configuration (schedule_type or schedule_cron) but triggers.schedule is false, so the schedule will be ignored. Set triggers.schedule: true or remove the schedule config. Jobs: ${join(", ", flatten([for p in local.projects : [for job in try(p.jobs, []) : "'${try(job.key, job.name)}' in project '${try(p.key, p.name)}'" if !try(job.triggers.schedule, false) && (try(job.schedule_type, null) != null || try(job.schedule_cron, null) != null)]]))}"
  }
}

# ── C-03: Global connections without protected: true ──────────────────────────
# Deleting a global connection detaches every environment that references it,
# which can silently break jobs. Protecting connections prevents accidental removal.

check "global_connections_protected" {
  assert {
    condition = length([
      for c in try(local.yaml_content.global_connections, []) :
      try(c.key, c.name)
      if !try(c.protected, false)
    ]) == 0
    error_message = "Best practice: the following global connections have protected: false. Deleting a connection detaches all environments that reference it. Add protected: true to prevent accidental removal. Connections: ${join(", ", [for c in try(local.yaml_content.global_connections, []) : try(c.key, c.name) if !try(c.protected, false)])}"
  }
}
