# Security policy

## Supported versions

AttestQL is a 0.x project and only its latest release is supported. A fix ships in the next
release rather than as a patch of an older one, and there are no long-lived branches to backport
to. The current release is 0.3.0.

| Version                 | Supported |
| ----------------------- | --------- |
| Latest 0.x release      | Yes       |
| Any earlier release     | No        |

## Reporting a vulnerability

Private vulnerability reporting is enabled on this repository. Use the Security tab, then "Report
a vulnerability". That opens a private advisory readable only by you and the maintainer. Please do
not open a public issue for a vulnerability.

A report is easiest to act on when it names the engine (PostgreSQL or SQLite), the version
`attestql --version` prints, the command you ran and what happened.

## What to expect

One person maintains this project outside of a support arrangement, so there is no response time
being promised here. A report gets a reply when it is read, and the advisory thread is where the
assessment, the fix and the release carrying it are recorded. A reporter is credited in the
advisory unless they ask not to be.

## Scope

AttestQL runs the SQL you give it against the database you point it at, under the role you supply,
which is why the README asks you to give it a read-only one. A statement doing what that role was
granted the right to do is the tool working as documented rather than a vulnerability. What is in
scope is AttestQL doing something the role, the flags or the documentation did not authorise:
writing where a read-only run should not, executing input that was meant to be recorded as data,
or leaking a credential into a record, a log or the site.
