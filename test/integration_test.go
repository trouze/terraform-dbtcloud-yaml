package test

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// skipIfNoIntegration skips the test unless RUN_INTEGRATION_TESTS=1 is set.
func skipIfNoIntegration(t *testing.T) {
	t.Helper()
	if os.Getenv("RUN_INTEGRATION_TESTS") == "" {
		t.Skip("skipping integration test; set RUN_INTEGRATION_TESTS=1 to run")
	}
}

// repoRoot returns the absolute path to the repository root (one level up from test/).
func repoRoot(t *testing.T) string {
	t.Helper()
	abs, err := filepath.Abs("../")
	require.NoError(t, err)
	return abs
}

// integrationVars builds the terraform variable map from environment variables.
// Required: DBT_CLOUD_ACCOUNT_ID, DBT_CLOUD_TOKEN
// Optional: DBT_CLOUD_HOST_URL (defaults to https://cloud.getdbt.com when unset)
func integrationVars(t *testing.T, yamlFixture string) map[string]interface{} {
	t.Helper()

	accountIDStr := os.Getenv("DBT_CLOUD_ACCOUNT_ID")
	require.NotEmpty(t, accountIDStr, "DBT_CLOUD_ACCOUNT_ID must be set")
	accountID, err := strconv.Atoi(accountIDStr)
	require.NoError(t, err, "DBT_CLOUD_ACCOUNT_ID must be a valid integer")

	token := os.Getenv("DBT_CLOUD_TOKEN")
	require.NotEmpty(t, token, "DBT_CLOUD_TOKEN must be set")

	vars := map[string]interface{}{
		"dbt_account_id": accountID,
		"dbt_token":      token,
		"yaml_file":      yamlFixture,
	}

	if hostURL := os.Getenv("DBT_CLOUD_HOST_URL"); hostURL != "" {
		vars["dbt_host_url"] = hostURL
	}

	return vars
}

// assertPositiveID checks that a key exists in the output map and its value is a positive number.
// Terraform serializes large integers as floats (e.g. "1.025871e+06"), so we parse via ParseFloat.
func assertPositiveID(t *testing.T, outputMap map[string]string, key string) {
	t.Helper()
	assert.Contains(t, outputMap, key, "expected key %q in output", key)
	val := outputMap[key]
	f, err := strconv.ParseFloat(val, 64)
	assert.NoError(t, err, "output %q value %q cannot be parsed as a number", key, val)
	assert.Greater(t, int(f), 0, "output %q should be a positive ID", key)
}

// TestIntegrationCoreWorkflow applies a single project with a development environment
// and a scheduled job, then verifies IDs are real and a second plan shows no changes.
func TestIntegrationCoreWorkflow(t *testing.T) {
	skipIfNoIntegration(t)

	root := repoRoot(t)
	opts := &terraform.Options{
		TerraformDir: root,
		Vars:         integrationVars(t, "tests/fixtures/integration-core.yml"),
		NoColor:      true,
	}

	defer terraform.Destroy(t, opts)
	terraform.InitAndApply(t, opts)

	projectIDs := terraform.OutputMap(t, opts, "project_ids")
	assertPositiveID(t, projectIDs, "tf_int_core")

	envIDs := terraform.OutputMap(t, opts, "environment_ids")
	assertPositiveID(t, envIDs, "tf_int_core_dev")

	jobIDs := terraform.OutputMap(t, opts, "job_ids")
	assertPositiveID(t, jobIDs, "tf_int_core_daily_run")

	// Idempotency: second plan must produce no changes (exit code 0).
	exitCode := terraform.PlanExitCode(t, opts)
	assert.Equal(t, 0, exitCode, "expected no changes after apply (exit code 0), got %d", exitCode)
}

// TestIntegrationMultiProject applies two projects with development environments,
// verifying that composite keys are correctly populated in real state.
func TestIntegrationMultiProject(t *testing.T) {
	skipIfNoIntegration(t)

	root := repoRoot(t)
	opts := &terraform.Options{
		TerraformDir: root,
		Vars:         integrationVars(t, "tests/fixtures/integration-multi-project.yml"),
		NoColor:      true,
	}

	defer terraform.Destroy(t, opts)
	terraform.InitAndApply(t, opts)

	projectIDs := terraform.OutputMap(t, opts, "project_ids")
	assert.Len(t, projectIDs, 2, "expected exactly 2 projects")
	assertPositiveID(t, projectIDs, "tf_int_alpha")
	assertPositiveID(t, projectIDs, "tf_int_beta")

	envIDs := terraform.OutputMap(t, opts, "environment_ids")
	assertPositiveID(t, envIDs, "tf_int_alpha_dev")
	assertPositiveID(t, envIDs, "tf_int_beta_dev")

	jobIDs := terraform.OutputMap(t, opts, "job_ids")
	assertPositiveID(t, jobIDs, "tf_int_alpha_nightly")

	exitCode := terraform.PlanExitCode(t, opts)
	assert.Equal(t, 0, exitCode, "expected no changes after apply (exit code 0), got %d", exitCode)
}

// TestIntegrationServiceToken applies a project and a service token, verifying
// that account-level resources are created and their IDs are populated.
func TestIntegrationServiceToken(t *testing.T) {
	skipIfNoIntegration(t)

	root := repoRoot(t)
	opts := &terraform.Options{
		TerraformDir: root,
		Vars:         integrationVars(t, "tests/fixtures/integration-service-tokens.yml"),
		NoColor:      true,
	}

	defer terraform.Destroy(t, opts)
	terraform.InitAndApply(t, opts)

	projectIDs := terraform.OutputMap(t, opts, "project_ids")
	assertPositiveID(t, projectIDs, "tf_int_svc")

	// service_token_ids is sensitive — read via OutputJson.
	serviceTokenJSON := terraform.OutputJson(t, opts, "service_token_ids")
	assert.NotEmpty(t, serviceTokenJSON, "service_token_ids output should not be empty")
	assert.Contains(t, serviceTokenJSON, "tf_int_svc_token", "expected key 'tf_int_svc_token' in service_token_ids")
}
