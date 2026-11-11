# Job Radar: setup (about 25 minutes, one time)

## 1. Create a GitHub account
github.com/signup. Confirm your email address.

## 2. Create a Gmail app password (this lets the script send email)
1. Open myaccount.google.com, Security.
2. Turn on 2-Step Verification if it is off.
3. Open myaccount.google.com/apppasswords, name it "job-radar", click Create.
4. Copy the 16-character code. You will not see it again.

## 3. Create the repository
GitHub, "+" (top right), New repository. Name: job-radar. Choose **Public** (free GitHub Pages needs it). Do not add a README. Create.

## 4. Upload the files
Unzip job-radar.zip. On the empty repository page click "uploading an existing file" and drag in
scraper.py, config.py, requirements.txt, dashboard_template.html, SETUP.md, and the folders data and docs.
Do NOT upload github-workflow.yml. Click Commit changes.

## 5. Create the schedule file
Add file, Create new file. In the name box type exactly: .github/workflows/job-alert.yml
(typing the slashes creates the folders). Open github-workflow.yml from the zip in a text editor, copy everything, paste it in. Commit changes.

## 6. Add your secrets
Settings, Secrets and variables, Actions, New repository secret. Add three:
- GMAIL_USER = aleksandarr.ha@gmail.com
- GMAIL_APP_PASSWORD = the 16-character code from step 2
- EMAIL_TO = aleksandarr.ha@gmail.com
Optional (more coverage): free keys from developer.adzuna.com, saved as ADZUNA_APP_ID and ADZUNA_APP_KEY.

## 7. Check write permission
Settings, Actions, General, Workflow permissions: choose "Read and write permissions", Save.

## 8. Turn on the website
Settings, Pages. Source: Deploy from a branch. Branch: main, folder: /docs. Save.
Your site will be https://YOUR-USERNAME.github.io/job-radar/

## 9. First run
Actions tab, "Job alert", Run workflow. It takes a few minutes. You get a setup email, and the website fills with jobs.
After that it runs by itself at about 06:00 and 18:00 German time.

## Changing things later
Open config.py on GitHub, click the pencil, edit, commit. Topics, search phrases, watchlist companies and TRAX keywords are all there.

## If something goes wrong
- No email: check spam once. Check the three secrets for typos. Open the failed run in the Actions tab and send me the log.
- Red X on a run: GitHub emails you automatically. That includes the case where the job board stops answering.
- Website shows "Waiting for the first run": finish step 9, then reload.
