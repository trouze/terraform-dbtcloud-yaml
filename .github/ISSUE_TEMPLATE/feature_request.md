name: Feature Request
description: Suggest an enhancement
labels: ["enhancement"]

body:
  - type: markdown
    attributes:
      value: |
        Thank you for suggesting a feature! Please describe what you'd like to see.

  - type: textarea
    id: problem
    attributes:
      label: Problem Statement
      description: What problem does this feature solve?
      placeholder: |
        I find it difficult to...
        Currently, I have to...
    validations:
      required: true

  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How would this feature work?
      placeholder: |
        It would be great if we could...
        The feature would allow users to...
    validations:
      required: true

  - type: textarea
    id: examples
    attributes:
      label: Example Usage
      description: Show how you'd like to use this feature
      render: yaml
      placeholder: |
        project:
          name: example
          # your example here

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: Any other approaches you've considered?

  - type: checkboxes
    id: checklist
    attributes:
      label: Checklist
      options:
        - label: I've searched for existing feature requests
          required: true
        - label: I've explained the use case clearly
          required: true
