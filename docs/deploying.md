# Putting Dumpit online, step by step

About 45 minutes, once. After that, every change that passes the tests goes live on its own.
Use a computer for steps 1 to 5 (a phone works, but copying is fiddly). Step 6 is on your phone.

Keep a private note open (Notes, Keep, a text file) to collect five things on the way:
**Anthropic key, database string, Gmail app password, Project ID, and later the app's address.**
Delete the note when you finish.

---

## Step 1: Private home for the code (2 min)

1. Go to **github.com/new**.
2. **Owner:** `miricoder`. **Repository name:** `dumpit`.
3. Select **Private**.
4. Leave *Add a README*, *.gitignore* and *license* off.
5. Click **Create repository**.
6. Tell Claude "repo created". It moves the app into the repo.

## Step 2: Anthropic key (5 min)

1. Go to **console.anthropic.com** and sign up.
2. Go to **Settings → Billing → Buy credits**, buy **$5** and pay by card.
3. Go to **Settings → API Keys → Create Key**. Name it `dumpit`, then click **Create**.
4. Click **Copy** and paste the key into your note. It starts with `sk-ant-`, and it is shown only once.

## Step 3: Database (5 min)

1. Go to **neon.tech** and click **Sign up**. *Continue with GitHub* is quickest.
2. Create a project:
   - **Project name:** `dumpit-staging`
   - **Region:** **AWS Europe Central 1 (Frankfurt)**
   - Click **Create**.
3. On the project page, click **Connect**.
4. Copy the connection string and paste it into your note. It looks like
   `postgresql://neondb_owner:…@ep-…eu-central-1.aws.neon.tech/neondb?sslmode=require`.

## Step 4: Sending the sign-in emails from your Gmail (3 min)

1. Go to **myaccount.google.com/security** and turn on **2-Step Verification**, if it is off.
2. Go to **myaccount.google.com/apppasswords**:
   - **App name:** `Dumpit`
   - Click **Create**.
3. Copy the 16 letters and paste them into your note, without the spaces.
4. In your note, write this line, using your own Gmail name and the 16 letters:

       smtps://YOURNAME%40gmail.com:ABCDEFGHIJKLMNOP@smtp.gmail.com:465

   `%40` stands for the `@` in your Gmail address. Type it exactly like that.

## Step 5: Google Cloud (15 min)

**5a. Project and billing**
1. Go to **console.cloud.google.com** and sign in. Accept the terms. If it offers a **free
   trial**, take it: that also sets up billing.
2. At the top left, click the **project picker** (next to the Google Cloud logo).
3. Click **New Project**. Name it `dumpit`, then click **Create**.
4. In the picker, select `dumpit`. Copy its **ID** into your note, for example `dumpit-472910`.
5. If you didn't take the free trial: go to **☰ → Billing → Link a billing account**,
   create one with your card, and link it.

**5b. Cloud Shell.** This is a terminal in your browser, with nothing to install.

1. At the top right of the console, click **>_** (*Activate Cloud Shell*). A terminal opens at
   the bottom. Click **Authorize** if asked.
2. Paste these lines one at a time, pressing Enter after each one. Put your Project ID in the
   first line.

       gcloud config set project YOUR-PROJECT-ID
       git clone -b dumpit https://github.com/miricoder/project-kit dumpit
       cd dumpit
       sh scripts/setup-cloud.sh miricoder/dumpit

   The last one takes 2 to 4 minutes. It ends by printing four lines, `GCP_PROJECT`,
   `GCP_REGION`, `GCP_WIF_PROVIDER` and `GCP_DEPLOY_SA`. Copy them into your note.
   *(The clone reads the setup scripts from the public copy. The deploy itself runs only from
   your private `miricoder/dumpit`.)*
3. Paste:

       sh scripts/setup-secrets.sh staging

   It asks for five things. Paste each one from your note and press Enter.
   **Nothing shows while you paste; that is normal.**

   | It asks for | Paste |
   |---|---|
   | Anthropic API key | `sk-ant-…` |
   | Postgres connection string | the `postgresql://…` line |
   | Email sending | the `smtps://…` line |
   | Sender address | your Gmail address |
   | The email that may sign in | the email you will sign in with |

## Step 6: Tell GitHub how to deploy (3 min)

1. Go to **github.com/miricoder/dumpit/settings/variables/actions**.
2. Click **New repository variable**, fill in **Name** and **Value** with the first line from
   your note (`GCP_PROJECT`), then click **Add variable**.
3. Repeat for `GCP_REGION`, `GCP_WIF_PROVIDER` and `GCP_DEPLOY_SA`.

These are not secrets; no key is stored in GitHub.

## Step 7: First deploy (8 min)

1. Go to **github.com/miricoder/dumpit/actions**, click **Dumpit CI**, then the run at the top.
2. Click **Re-run all jobs**, then **Re-run jobs**.
3. Wait until **test**, **Container image builds** and **deploy-staging** are green.
4. The run's page shows **Deployed 0.1.0-… to staging: https://dumpit-staging-….run.app**.
   Copy that address into your note.
5. Back in Cloud Shell, paste this, with your email:

       sh scripts/setup-uptime.sh staging YOUR-EMAIL

   You then get an email if the app ever stops answering.

## Step 8: Install it

**Android phone, Chrome**
1. Open **Chrome** and go to the address from step 7.
2. Type your email and tap **Send sign-in link**.
3. Open the email from Dumpit and tap the link. It opens in Chrome, and you're in.
4. Tap **⋮** (top right), then **Install app**. On some phones it says **Add to Home screen → Install**.
5. Dumpit now has its own icon. Open it from there.

**Computer, Chrome or Edge**
1. Open the address and sign in the same way.
2. Click the **install icon** at the right end of the address bar (a screen with a ↓), then
   **Install**. It opens in its own window, and you can pin it to your taskbar or dock.

**iPhone:** not yet. An app installed to the iPhone Home Screen keeps its own sign-in,
separate from Safari, so the emailed link signs in Safari instead of the app. This needs a
sign-in code to type into the app, which is a small change still to build.

---

## After that

| When | What happens |
|---|---|
| Claude builds a change and it passes the tests | staging updates by itself in about 5 minutes |
| You next open the app | "Updated to 0.1.0-…" and what changed |
| The app is open when an update lands | **Update now** |
| Something breaks | Cloud Run → `dumpit-staging` → **Revisions** → the previous one → **Manage traffic → 100%** |
| Spending passes €1 | Google emails you |
| A library has an update | a pull request appears in GitHub each week; CI tests it |
| Going live for real (production) | `/project-kit:launch` walks you through it: a second Neon project, `setup-secrets.sh production`, then a release tag |
