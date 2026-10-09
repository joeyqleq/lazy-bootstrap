# Security

The tracked `env` file contains placeholders only. Do not commit live credentials.

For deployment, edit a private copy locally, upload it beside `bootstrap.sh`, and rename it to `.env` on the target VM.

If a credential is ever committed, rotate it immediately. Rewriting the latest commit does not remove it from Git history.
