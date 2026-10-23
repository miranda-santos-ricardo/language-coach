# Run from repo root. Review before sharing; never include .env, secrets or database dumps.
$paths = @(
  'backend/app/models/practice_session.py',
  'backend/app/models/conversation_turn.py',
  'backend/app/services/conversation_service.py',
  'backend/app/api/routes/practice_sessions.py',
  'backend/app/api/routes/conversation.py',
  'backend/app/db/session.py'
)
$existing = $paths | Where-Object { Test-Path $_ }
Write-Host 'Files found:'; $existing
if ($existing.Count -gt 0) { Compress-Archive -Path $existing -DestinationPath phase7_step54a_repository_sources.zip -Force }
Write-Host 'Check paths, then review the zip before sharing. Missing paths can be located with: git ls-files backend | Select-String "conversation|practice_session|auth|database"'
