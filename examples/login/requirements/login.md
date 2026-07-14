# Login

## Overview

Users sign in with an email address and a password to reach their account
dashboard.

## Email field (CTRL-EMAIL)

- Type: textbox
- Required: yes
- Behavior: Leaving the field blank and submitting shows "Email is required" and blocks submission.

## Submit button (CTRL-SUBMIT)

- Type: button
- Behavior: Disabled while the form has validation errors; enabled once email and password are both valid.

## Business rules

- The submit button must stay disabled until both the email and password fields pass validation.
- Leaving the email field blank blocks form submission with an inline error.

## Risks

- Users may not notice the inline validation error and repeatedly click a disabled button.

## Open questions

None.
