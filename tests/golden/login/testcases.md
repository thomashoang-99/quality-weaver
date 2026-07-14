---
status: approved
case_count: 2
---
# Test Cases

## TC-001: Blank email blocks submission

- Requirement traceability: via OUT-001
- Coverage: [&quot;COV-001&quot;]
- Priority: high
- Tags: [&quot;login&quot;, &quot;validation&quot;]

### Preconditions

1. User is on the login page

### Test Data

1. email = empty
2. password = empty

### Steps

| Step | Action | Expected Result |
| ---: | --- | --- |
| 1 | Leave the email field blank and submit the form | The &quot;Email is required&quot; error appears and the form is not submitted |

## TC-002: Submit button disabled until form valid

- Requirement traceability: via OUT-002
- Coverage: [&quot;COV-002&quot;]
- Priority: high
- Tags: [&quot;action-controls&quot;, &quot;login&quot;]

### Preconditions

1. User is on the login page

### Test Data

1. email = invalid
2. password = empty

### Steps

| Step | Action | Expected Result |
| ---: | --- | --- |
| 1 | Enter an invalid email and leave password blank | Submit button remains disabled |
| 2 | Enter a valid email and password | Submit button becomes enabled |
