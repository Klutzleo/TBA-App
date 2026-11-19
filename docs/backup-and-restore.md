# Backups and restoring TBA

Railway's Hobby plan has no database backups (the Backups tab says to upgrade to Pro), so TBA backs itself up.

## What runs

- **Nightly backup** (`.github/workflows/backup.yml`, about 2 a.m. Pacific): dumps the production Postgres with `pg_dump` 17, checks the dump is real,
  encrypts it with AES-256, and uploads it to the private Cloudflare R2 bucket `tba-backups`. It keeps 14 daily copies (`daily/`) and 8 weekly
  copies (`weekly/`, taken on Sundays). If a run fails, GitHub emails the repo owner.
- **Uptime check** (`.github/workflows/uptime.yml`, every 10 minutes): the landing page, `/health`, and a public page that reads the database. It
  retries for about 3 minutes before failing, so a normal deploy restart does not raise an alarm. A failed run emails the repo owner.
- **Restore drill** (`.github/workflows/restore-drill.yml`, the 1st of every month, or run it by hand): downloads the newest backup from R2,
  decrypts it, restores it into a throwaway PostgreSQL 17, and checks the tables, users, campaigns and characters came back. A failure emails the repo owner.
- A manual dump from 2026-11-19 is on Jason's PC in `C:\Users\jgermino\TBA-backups\` (contains personal data: keep it private).

## Secrets the backup needs (GitHub: Settings > Secrets and variables > Actions)

| Secret | What it is |
|---|---|
| `BACKUP_DATABASE_URL` | the production database's PUBLIC connection URL (Railway: Postgres service > `DATABASE_PUBLIC_URL`). **If the database password is ever rotated, update this secret too**, or backups fail. |
| `R2_ENDPOINT` | `https://<your-cloudflare-account-id>.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | an R2 API token limited to the `tba-backups` bucket, read and write |
| `BACKUP_PASSPHRASE` | the passphrase that encrypts every backup. **Keep a copy in your password manager. Without it the backups cannot be opened.** |

## Restore: get the data back

You need: the passphrase, the PostgreSQL 17 command-line tools (`pg_restore`, `createdb`), and an empty Postgres 17 database to restore into.

1. **Download** the backup you want from R2 (`tba-backups/daily/tba-YYYY-MM-DD.dump.enc`, or `weekly/`): Cloudflare dashboard > R2 > `tba-backups`, or `aws s3 cp`.
2. **Decrypt it** (the passphrase goes in an environment variable so it never appears on the command line):
   ```
   export BACKUP_PASSPHRASE='your passphrase'
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in tba-2026-11-19.dump.enc -out tba.dump -pass env:BACKUP_PASSPHRASE
   ```
   A wrong passphrase fails with "bad decrypt".
3. **Restore into an empty database:**
   ```
   createdb -h HOST -U USER tba_restored
   pg_restore --no-owner --no-privileges --exit-on-error -h HOST -U USER -d tba_restored tba.dump
   ```
4. **Check it**: count the rows in `users`, `campaigns`, `characters` and `messages`, and compare with what you expect.

## If production is lost: bring TBA back

1. In Railway, add a new Postgres service to the project. Restore the latest backup into it (steps above), using its public connection URL.
2. Point the app at it: set `DATABASE_URL` on the TBA-App service to the new database's URL (Railway reference variables work). The app redeploys and reconnects.
3. Update the `BACKUP_DATABASE_URL` GitHub secret to the new database, so nightly backups keep working.
4. Check: `/health`, a login, a campaign page. `run_migrations.py` runs on every deploy and will apply anything missing.
5. The weekly copies are the fallback if the newest daily is somehow bad.

## Test it

A backup you have never restored is a hope, not a backup. Once a month, do steps 1 to 4 into a scratch database and check the counts. The
2026-11-19 manual dump was restored into a scratch Postgres 17 and matched production exactly: 45 tables, 1,604 rows, 143 indexes, 135 constraints.

## Good to know

- The backup reaches the database through Railway's public TCP proxy, which is protected by the database password.
- Backups contain real user data (emails, password hashes, notification keys). They are encrypted in R2; the decrypted `.dump` file is not,
  so delete it when you are done and never commit it.
- R2 bucket access is limited to the one bucket. Rotate the R2 token if it is ever exposed.
- GitHub can pause scheduled workflows in a repo with no activity for 60 days. This repo is active; if the emails ever stop, check the Actions tab.
