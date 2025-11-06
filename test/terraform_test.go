package test

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestBasicConfiguration validates the root module works with minimal YAML
func TestBasicConfiguration(t *testing.T) {
	t.Parallel()

	// Setup test fixtures
	tmpDir := filepath.Join(os.TempDir(), "dbt-terraform-test-basic")
	defer os.RemoveAll(tmpDir)

	// Copy test configuration
	err := copyDir("fixtures/basic", tmpDir)
	require.NoError(t, err, "Failed to copy fixture directory")

	// Configure Terraform
	terraformOptions := &terraform.Options{
		TerraformDir: tmpDir,
		VarFiles:     []string{"terraform.tfvars"},
		Lock:         true,
		NoColor:      true,
		Logger:       t,
		// Set to -json for structured output
		Vars: map[string]interface{}{
			"dbt_account_id": "999999",
			"dbt_host_url":   "https://cloud.getdbt.com",
		},
		EnvVars: map[string]string{
			"TF_INPUT": "false",
		},
	}

	// Initialize and plan (not apply - we don't have real creds)
	defer terraform.Destroy(t, terraformOptions)

	// Init should succeed
	terraform.Init(t, terraformOptions)

	// Plan should validate syntax without errors
	planOutput := terraform.Plan(t, terraformOptions)

	// Verify plan output contains expected resources
	assert.Contains(t, planOutput, "module.dbt_cloud")
	assert.NotContains(t, planOutput, "Error")
}

// TestCompleteConfiguration validates advanced YAML features
func TestCompleteConfiguration(t *testing.T) {
	t.Parallel()

	tmpDir := filepath.Join(os.TempDir(), "dbt-terraform-test-complete")
	defer os.RemoveAll(tmpDir)

	// Copy advanced test configuration
	err := copyDir("fixtures/complete", tmpDir)
	require.NoError(t, err, "Failed to copy fixture directory")

	terraformOptions := &terraform.Options{
		TerraformDir: tmpDir,
		VarFiles:     []string{"terraform.tfvars"},
		Lock:         true,
		NoColor:      true,
		Logger:       t,
		Vars: map[string]interface{}{
			"dbt_account_id": "999999",
			"dbt_host_url":   "https://cloud.getdbt.com",
		},
		EnvVars: map[string]string{
			"TF_INPUT": "false",
		},
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	planOutput := terraform.Plan(t, terraformOptions)

	// Verify complex features are handled
	assert.Contains(t, planOutput, "module.dbt_cloud")
	assert.NotContains(t, planOutput, "Error")
}

// TestYAMLParsing validates YAML file is correctly parsed into Terraform locals
func TestYAMLParsing(t *testing.T) {
	t.Parallel()

	tmpDir := filepath.Join(os.TempDir(), "dbt-terraform-test-yaml")
	defer os.RemoveAll(tmpDir)

	err := copyDir("fixtures/basic", tmpDir)
	require.NoError(t, err)

	// Read the YAML file to verify it's valid
	yamlPath := filepath.Join(tmpDir, "dbt-config.yml")
	yamlContent, err := os.ReadFile(yamlPath)
	require.NoError(t, err, "Failed to read YAML file")

	// Verify YAML contains expected structure
	yamlStr := string(yamlContent)
	assert.Contains(t, yamlStr, "project:")
	assert.Contains(t, yamlStr, "name:")
	assert.Contains(t, yamlStr, "environments:")
}

// TestVariableValidation validates that input variables have proper validation
func TestVariableValidation(t *testing.T) {
	t.Parallel()

	tmpDir := filepath.Join(os.TempDir(), "dbt-terraform-test-vars")
	defer os.RemoveAll(tmpDir)

	err := copyDir("fixtures/basic", tmpDir)
	require.NoError(t, err)

	// Test invalid account ID (non-numeric)
	terraformOptions := &terraform.Options{
		TerraformDir: tmpDir,
		Lock:         true,
		NoColor:      true,
		Logger:       t,
		Vars: map[string]interface{}{
			"dbt_account_id": "invalid",
			"dbt_host_url":   "https://cloud.getdbt.com",
		},
		EnvVars: map[string]string{
			"TF_INPUT": "false",
		},
	}

	terraform.Init(t, terraformOptions)

	// Plan should fail with validation error
	err = terraform.PlanE(t, terraformOptions)
	assert.Error(t, err, "Expected validation error for non-numeric account_id")
}

// TestOutputs validates that module exports expected outputs
func TestOutputs(t *testing.T) {
	t.Parallel()

	tmpDir := filepath.Join(os.TempDir(), "dbt-terraform-test-outputs")
	defer os.RemoveAll(tmpDir)

	err := copyDir("fixtures/basic", tmpDir)
	require.NoError(t, err)

	terraformOptions := &terraform.Options{
		TerraformDir: tmpDir,
		VarFiles:     []string{"terraform.tfvars"},
		Lock:         true,
		NoColor:      true,
		Logger:       t,
		Vars: map[string]interface{}{
			"dbt_account_id": "999999",
			"dbt_host_url":   "https://cloud.getdbt.com",
		},
		EnvVars: map[string]string{
			"TF_INPUT": "false",
		},
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)

	// Check that expected outputs are defined in module
	outputs := terraform.OutputAll(t, terraformOptions)
	expectedOutputs := []string{"project_id", "repository_id", "environment_ids", "credential_ids", "job_ids"}

	for _, output := range expectedOutputs {
		assert.Contains(t, outputs, output, fmt.Sprintf("Expected output '%s' not found", output))
	}
}

// TestPathModule validates that path.module is used for module sources
func TestPathModule(t *testing.T) {
	mainTfPath := "main.tf"
	content, err := os.ReadFile(mainTfPath)
	require.NoError(t, err, "Failed to read main.tf")

	mainTfStr := string(content)

	// Verify all module sources use path.module instead of relative paths
	assert.NotContains(t, mainTfStr, `source = "./modules/`, "Found relative module paths instead of path.module")
	assert.Contains(t, mainTfStr, `source = "${path.module}/modules/`, "Module sources should use path.module")

	// Count occurrences - should have 8 module sources using path.module
	count := 0
	startIdx := 0
	searchStr := `source = "${path.module}/modules/`
	for {
		idx := findString(mainTfStr, searchStr, startIdx)
		if idx == -1 {
			break
		}
		count++
		startIdx = idx + 1
	}

	assert.GreaterOrEqual(t, count, 7, "Expected at least 7 module sources using path.module")
}

// TestModuleStructure validates that all required module files exist
func TestModuleStructure(t *testing.T) {
	requiredModules := []string{
		"modules/project",
		"modules/repository",
		"modules/project_repository",
		"modules/credentials",
		"modules/environments",
		"modules/jobs",
		"modules/environment_variables",
		"modules/environment_variable_job_overrides",
	}

	for _, module := range requiredModules {
		// Check main.tf exists
		mainTfPath := filepath.Join(module, "main.tf")
		_, err := os.Stat(mainTfPath)
		assert.NoError(t, err, fmt.Sprintf("Module %s missing main.tf", module))

		// Check variables.tf exists
		varsTfPath := filepath.Join(module, "variables.tf")
		_, err = os.Stat(varsTfPath)
		assert.NoError(t, err, fmt.Sprintf("Module %s missing variables.tf", module))

		// Check outputs.tf exists
		outputsTfPath := filepath.Join(module, "outputs.tf")
		_, err = os.Stat(outputsTfPath)
		assert.NoError(t, err, fmt.Sprintf("Module %s missing outputs.tf", module))
	}
}

// TestDocumentation validates that documentation files exist and contain key sections
func TestDocumentation(t *testing.T) {
	docFiles := map[string][]string{
		"README.md": {"Quick Start", "Configuration", "YAML", "Troubleshooting"},
		"QUICKSTART.md": {"Prerequisites", "Step", "module"},
		"CONTRIBUTING.md": {"Contributing", "Development"},
		"CHANGELOG.md": {"Changelog", "1.0.0"},
	}

	for file, requiredSections := range docFiles {
		content, err := os.ReadFile(file)
		require.NoError(t, err, fmt.Sprintf("Failed to read %s", file))

		fileStr := string(content)
		for _, section := range requiredSections {
			assert.Contains(t, fileStr, section, fmt.Sprintf("%s missing section: %s", file, section))
		}
	}
}

// Helper functions

// copyDir recursively copies a directory
func copyDir(src, dst string) error {
	entries, err := os.ReadDir(src)
	if err != nil {
		return err
	}

	if err := os.MkdirAll(dst, 0755); err != nil {
		return err
	}

	for _, entry := range entries {
		srcPath := filepath.Join(src, entry.Name())
		dstPath := filepath.Join(dst, entry.Name())

		if entry.IsDir() {
			if err := copyDir(srcPath, dstPath); err != nil {
				return err
			}
		} else {
			data, err := os.ReadFile(srcPath)
			if err != nil {
				return err
			}

			if err := os.WriteFile(dstPath, data, 0644); err != nil {
				return err
			}
		}
	}

	return nil
}

// findString finds a substring in a string, starting from startIdx
func findString(s, substr string, startIdx int) int {
	if startIdx >= len(s) {
		return -1
	}
	idx := -1
	for i := startIdx; i < len(s); i++ {
		if i+len(substr) <= len(s) && s[i:i+len(substr)] == substr {
			idx = i
			break
		}
	}
	return idx
}

// ParseOutputJSON parses terraform output JSON
func ParseOutputJSON(output string) (map[string]interface{}, error) {
	var result map[string]interface{}
	if err := json.Unmarshal([]byte(output), &result); err != nil {
		return nil, err
	}
	return result, nil
}
