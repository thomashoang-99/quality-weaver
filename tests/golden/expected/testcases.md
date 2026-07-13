---
status: approved
case_count: 2
---
# Test Cases

## TC-001: pipe \| next \# heading &lt;script&gt;alert\(1\)&lt;/script&gt; \[link\]\(javascript\:alert\(1\)\) \*\*bold\*\* \`tick\`

- Requirement traceability: via OUT-001
- Coverage: COV-001
- Priority: high
- Tags: login

### Preconditions

1. User is on the login page

### Test Data

1. email = empty

### Steps

| Step | Action | Expected Result |
| ---: | --- | --- |
| 1 | pipe \| next \# heading &lt;script&gt;alert\(1\)&lt;/script&gt; \[link\]\(javascript\:alert\(1\)\) \*\*bold\*\* \`tick\` | pipe \| next \# heading &lt;script&gt;alert\(1\)&lt;/script&gt; \[link\]\(javascript\:alert\(1\)\) \*\*bold\*\* \`tick\` |

## TC-002: Session timeout

- Requirement traceability: via OUT-002
- Coverage: COV-002
- Priority: high
- Tags: login

### Preconditions

1. User is on the login page

### Test Data

1. email = empty

### Steps

| Step | Action | Expected Result |
| ---: | --- | --- |
| 1 | Submit the form | A validation message appears |
