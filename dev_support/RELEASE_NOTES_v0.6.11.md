# Release Notes v0.6.11

Date: 2026-01-09

## Summary

This is a patch release focused on ensuring scheduled dbt Cloud jobs migrate with correct schedule configuration.

## Fixed

- **Jobs: schedule normalization**
  - Normalizer now reads schedule fields from the nested Jobs API shape:
    - `settings.schedule.date` (e.g., `type`, `days`, `cron`)
    - `settings.schedule.time` (e.g., `type`, `interval`, `hours`)
  - Prevents invalid Terraform/provider attribute combinations by:
    - Only emitting `schedule_cron` for `custom_cron`
    - Selecting `schedule_hours` vs `schedule_interval` based on `schedule.time.type`
    - Omitting all schedule fields unless `triggers.schedule` is true


